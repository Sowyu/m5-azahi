#!/usr/bin/env python3
"""Link the guarded loader against a pinned upstream tree. Never install or boot.

Requires cached Cargo dependencies and the aarch64-unknown-none-softfloat target.
Keeps sources, objects, ELF files and logs, including after a failed check.
No kernel, initrd, device tree or disk identity is added.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parent.parent
BASE_COMMIT = '4184923ffb2dff079b384d6a32cc02142aa14572'
RUST_TARGET = 'aarch64-unknown-none-softfloat'
SMP_INPUTS = {
    'm1n1-raw.ld': '969e1954119e54c25f358d03983a9d84fcc5f6dcebe19e40f79fa8e18785a122',
    'm1n1.ld': '0385573f93e53a006a1cd6943bd7272e6f081bfd8e98dfc764a5138412b53d36',
    'src/kboot.c': 'ec7eab5a80e5144547ae73410da2827d2065a636db74f50962386eb5056e951b',
    'src/main.c': 'eb7240c067251855223f8ba1708a1f2b2ed81bc82bc4839672e6995f21d08ce2',
    'src/memory.c': 'a016b37ea588a984b2d1b26d0592fa2e1694c837854c9dcd02839595c928bd2d',
    'src/smp.c': 'cb5c44cf90264d92927523712716e382acb70c453a147d34877880779f8d1af3',
    'src/smp.h': 'd4bd759b232d47930893c4d0fb90280935741929e4e4dca5a15654fb0a316c83',
    'src/smp_asm.h': None,
    'src/start.S': 'a79f7ef0ec8c20fd2f82a62525d1b7d14fca6e07e8d7cc286523cef2d99e91ff',
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def apply_smp_refactor(source, run_logged):
    for name, expected in SMP_INPUTS.items():
        path = source / name
        if (path.exists() if expected is None else not path.is_file() or digest(path) != expected):
            raise ValueError(f'SMP refactor input differs from reviewed source: {name}')
    patch = ROOT / 'standalone-loader/smp-shared-state.patch'
    command = ['patch', '--batch', '--forward', '--fuzz=0', '--no-backup-if-mismatch',
               '-p1', '-i', str(patch)]
    run_logged(command + ['--dry-run'], 'smp-patch-check.log')
    run_logged(command, 'smp-patch.log')
    return {'patch_sha256': digest(patch),
            'source_sha256': {name: digest(source / name) for name in SMP_INPUTS}}


def check_smp_layout(symbols, sizes):
    start, end = symbols['_smp_shared_start'], symbols['_smp_shared_end']
    if start % 0x10000 or end % 0x10000 or start >= end:
        raise ValueError('SMP shared section is empty or not 64 KiB aligned')
    if not (symbols['_data_start'] == start < end <= symbols['_file_end'] <= symbols['_bss_start']):
        raise ValueError('SMP shared section is outside initialized data')
    for name, size in (('_reset_stack', 8), ('_reset_stack_el1', 8), ('wfe_mode', 1),
                       ('target_cpu', 4), ('spin_table', 24 * 64),
                       ('smp_reset_stacks', 24 * 16), ('boot_cpu_idx', 4), ('boot_cpu_mpidr', 8)):
        if sizes.get(name) != size or not start <= symbols[name] <= end - size:
            raise ValueError(f'Shared CPU state is missing or outside its section: {name}')
    for name, count in (('secondary_stacks', 24), ('secondary_stacks_el3', 4)):
        address, size = symbols[name], count * 0x10000
        if (sizes.get(name) != size or address % 0x4000 or
                not symbols['_bss_start'] <= address <= symbols['_bss_end'] - size or
                symbols['_bss_end'] > symbols['_end']):
            raise ValueError(f'Static stacks are misaligned or outside reserved loader BSS: {name}')
    return {'shared_start': start, 'shared_end': end,
            'static_stack_bytes': 28 * 0x10000, 'reserved_loader_end': symbols['_end']}


def check_link(headers, output, compiler, smp_refactor=False):
    headers, output = headers.resolve(), output.resolve()
    if output.exists():
        raise ValueError(f'Output already exists; choose a new directory: {output}')
    compiler_path = shutil.which(compiler)
    if not compiler_path or not Path(compiler_path).name.endswith('gcc'):
        raise ValueError('Pass the AArch64 GCC executable, with a name ending in gcc')
    compiler_path = Path(compiler_path).absolute()
    prefix = str(compiler_path)[:-3]
    for tool in ('git', 'make', 'cargo', 'rustc', prefix + 'ld', prefix + 'nm', prefix + 'objdump'):
        if not shutil.which(tool):
            raise ValueError(f'Required tool missing: {tool}')
    target_lib = subprocess.check_output(
        ['rustc', '--print', 'target-libdir', '--target', RUST_TARGET], text=True).strip()
    if not Path(target_lib).is_dir():
        raise ValueError(f'Rust target missing; install with: rustup target add {RUST_TARGET}')
    archive = subprocess.check_output(
        ['git', '-C', str(headers), 'archive', '--format=tar', BASE_COMMIT])

    # Reuse the reviewed patch application, input pins and component checks.
    component_build = runpy.run_path(str(ROOT / 'smp/build-offline.py'))['build']
    component_build(headers, output / 'components', str(compiler_path))
    (output / 'base-source.tar').write_bytes(archive)
    source = output / 'source'
    source.mkdir()
    with tarfile.open(fileobj=io.BytesIO(archive)) as tf:
        tf.extractall(source, filter='data')

    archived = ROOT / 'research-archive/standalone-loader/m1n1-20260911'
    current = ROOT / 'standalone-loader/m1n1-20260911'
    overrides = {}
    for origin, names in (
        (archived, ('src/main.c', 'src/payload.c', 'src/nvme.c', 'src/cpufreq.c')),
        (current, ('src/kboot.c', 'src/azahi_pcie.c', 'src/azahi_pcie.h')),
        (output / 'components', ('Makefile', 'src/smp.c', 'src/pmgr.c', 'src/pmgr.h',
                                'src/azahi_smp.c', 'src/azahi_smp.h',
                                'src/azahi_standalone.c', 'src/azahi_standalone.h')),
    ):
        for name in names:
            shutil.copyfile(origin / name, source / name)
            overrides[name] = {'source': str(origin / name), 'sha256': digest(source / name)}
    makefile = source / 'Makefile'
    text = makefile.read_text()
    anchor = '\tazahi_smp.o \\\n'
    if text.count(anchor) != 1:
        raise ValueError('Expected one diagnostic object in the patched Makefile')
    text = text.replace(anchor, anchor + '\tazahi_pcie.o \\\n')
    # Retain implicit intermediates too. Never invoke the upstream clean target.
    makefile.write_text(text + '\n.SECONDARY:\n')
    build = source / 'build'
    build.mkdir()
    (build / 'build_tag.h').write_text('#define BUILD_TAG "azahi-offline-link-check"\n')
    (build / 'build_cfg.h').write_text('')

    commands = []
    def run_logged(command, filename, env=None):
        commands.append(command)
        with (output / filename).open('x') as log:
            subprocess.run(command, cwd=source, env=env, stdout=log,
                           stderr=subprocess.STDOUT, check=True)

    refactor = apply_smp_refactor(source, run_logged) if smp_refactor else None
    run_logged(['cargo', 'build', '--locked', '--offline', '--target', RUST_TARGET,
                '--lib', '--release', '--manifest-path', 'rust/Cargo.toml',
                '--target-dir', 'build'], 'rust.log', dict(os.environ, RUSTC_BOOTSTRAP='1'))
    shutil.copyfile(build / RUST_TARGET / 'release/librust.a', build / 'librust.a')
    run_logged(['make', '-j4', '-o', 'build-tag', '-o', 'build-cfg', '-o', 'build/librust.a',
                f'TOOLCHAIN={compiler_path.parent}/', f'ARCH={compiler_path.name[:-3]}',
                'build/m1n1.elf', 'build/m1n1-raw.elf'], 'link.log')

    artifacts = {}
    required = ('azahi_standalone_run', 'azahi_smp_diag', 'azahi_pcie_init',
                'pmgr_lookup_device_addr', 'payload_run', 'smp_start_secondaries', 'nvme_init')
    for name in ('m1n1.elf', 'm1n1-raw.elf'):
        path = build / name
        elf = path.read_bytes()
        if elf[:6] != b'\x7fELF\x02\x01' or int.from_bytes(elf[18:20], 'little') != 183:
            raise ValueError(f'Not an AArch64 ELF: {name}')
        if subprocess.check_output([prefix + 'nm', '-u', str(path)], text=True).strip():
            raise ValueError(f'Unresolved symbols in {name}')
        symbols = subprocess.check_output([prefix + 'nm', '-n', str(path)], text=True)
        (output / (name + '.symbols')).write_text(symbols)
        parsed = {fields[2]: int(fields[0], 16) for line in symbols.splitlines()
                  if len(fields := line.split()) == 3 and fields[1] != 'U'}
        if any(symbol not in parsed for symbol in required):
            raise ValueError(f'Custom loader entry or guard missing from {name}')
        if name == 'm1n1-raw.elf' and (parsed['_base'] != 0 or parsed['_start'] != 0x800):
            raise ValueError('Raw entry layout changed')
        for marker in (b'AZAHI_ONE_CORE', b'PRIVATE-LINUX-PARTUUID-NOT-CONFIGURED'):
            if marker not in elf:
                raise ValueError(f'Guard marker missing from {name}')
        artifacts[name] = {'sha256': digest(path), 'bytes': len(elf),
                           'entry': parsed['_start'], 'payload_offset': parsed['_payload_start']}
        if smp_refactor:
            sized = subprocess.check_output([prefix + 'nm', '-n', '-S', str(path)], text=True)
            (output / (name + '.sizes')).write_text(sized)
            sizes = {fields[3]: int(fields[1], 16) for line in sized.splitlines()
                     if len(fields := line.split()) == 4}
            artifacts[name]['smp_layout'] = check_smp_layout(parsed, sizes)
    disassemble = ['payload_run', 'azahi_standalone_run', 'smp_start_secondaries', 'nvme_init']
    if smp_refactor:
        disassemble += ['smp_init', 'cpu_reset', 'smp_secondary_entry', 'mmu_add_default_mappings']
    for symbol in disassemble:
        run_logged([prefix + 'objdump', '-d', '--disassemble=' + symbol,
                    str(build / 'm1n1-raw.elf')], symbol + '.s')

    manifest = {
        'status': 'complete offline link check; not an installed or hardware-tested loader',
        'base_commit': BASE_COMMIT,
        'base_archive_sha256': hashlib.sha256(archive).hexdigest(),
        'component_manifest_sha256': digest(output / 'components/manifest.json'),
        'source_overrides': overrides, 'makefile_sha256': digest(makefile),
        'compiler': subprocess.check_output([str(compiler_path), '--version'], text=True).splitlines()[0],
        'rustc': subprocess.check_output(['rustc', '--version'], text=True).strip(),
        'cargo_lock_sha256': digest(source / 'rust/Cargo.lock'),
        'commands': commands, 'artifacts': artifacts,
        'payload_included': False, 'installed': False, 'default_secondary_start': False,
        'smp_refactor': refactor,
    }
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(f'Both loader ELF files linked with no undefined symbols. {output / "manifest.json"}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--m1n1', required=True, type=Path, help='Local Git tree containing the pinned commit')
    parser.add_argument('--output', required=True, type=Path, help='New external build directory')
    parser.add_argument('--cc', default='aarch64-linux-gnu-gcc')
    parser.add_argument('--smp-refactor', action='store_true',
                        help='Apply the optional guarded upstream shared-state and stack backport')
    args = parser.parse_args()
    try:
        check_link(args.m1n1, args.output, args.cc, args.smp_refactor)
    except (ValueError, OSError, subprocess.CalledProcessError, tarfile.TarError) as exc:
        parser.exit(1, f'Full link check failed; any outputs are retained: {exc}\n')


if __name__ == '__main__':
    main()
