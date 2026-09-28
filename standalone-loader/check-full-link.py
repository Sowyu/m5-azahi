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


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_link(headers, output, compiler):
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
    for symbol in ('payload_run', 'azahi_standalone_run', 'smp_start_secondaries', 'nvme_init'):
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
    }
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(f'Both loader ELF files linked with no undefined symbols. {output / "manifest.json"}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--m1n1', required=True, type=Path, help='Local Git tree containing the pinned commit')
    parser.add_argument('--output', required=True, type=Path, help='New external build directory')
    parser.add_argument('--cc', default='aarch64-linux-gnu-gcc')
    args = parser.parse_args()
    try:
        check_link(args.m1n1, args.output, args.cc)
    except (ValueError, OSError, subprocess.CalledProcessError, tarfile.TarError) as exc:
        parser.exit(1, f'Full link check failed; any outputs are retained: {exc}\n')


if __name__ == '__main__':
    main()
