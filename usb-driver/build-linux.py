#!/usr/bin/env python3
"""Build USB candidates on Linux from the pinned Fedora devel RPM, without installation.

Requires an AArch64 GCC 16.1 toolchain, a host C compiler, bsdtar and dtc.
--with-input also builds the DockChannel input candidate from this repository.
--dockchannel-source adds the optional FIFO timeout fix from pinned kernel source.
--smc-source accepts the pinned macsmc.c and applies the offline SMC patch.
--smc-power-source also prepares the battery firmware compatibility backport.
--nvme-header also builds the public J714s read-only ANS/SART candidates.
--nvme-core-source builds a paired NVMe core/Apple firmware compatibility experiment.
All intermediate files remain in a new output directory, including on failure.
This follows the existing manual module recipe, not a full kernel rebuild.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys

HERE = Path(__file__).resolve().parent
KERNEL = '7.0.13-400.asahi.fc44.aarch64+16k'
RPM_SHA256 = 'ad835398b8d443619030c5baccc79246fc97d175fc2d17633738d35fd0319c0a'
CONFIG_SHA256 = '997a0fb73eb02e81a364cc3a29d81a3c6cc8c17b1980f3b9d6bb65795ace23b3'
SYMVERS_SHA256 = '491c78595b727d87994f82d56d81a94b4db18b195102a163b8deaedeede2b036'
SMC_SOURCE_SHA256 = '6a8004c39af84de5757ffac8453b3d9822a3e590ff6ac3bf7b1415f52373af0a'
SMC_POWER_SOURCE_SHA256 = '96b6da14e998a9872d11da9c634570c598f8dcbc7d9c305f6578b775b8803935'
DOCKCHANNEL_SOURCE_SHA256 = '83cc73986312a06d99f7e5828a078964a581be00dc5826195e4622d5c6a7bede'
NVME_HEADER_SHA256 = '0ed6fec6c7e7067fca642241e1c8710391f7da949c41759b10ccfa45010b92cf'
NVME_CORE_PARTS = ('core', 'ioctl', 'sysfs', 'pr', 'trace', 'multipath', 'zns', 'hwmon', 'auth')
NVME_CORE_MARKER = 'nvme_azahi_admin_page_align_v1'
SART_EXPORTS = {'devm_apple_sart_get', 'apple_sart_add_allowed_region',
                'apple_sart_remove_allowed_region'}
DOCKCHANNEL_EXPORTS = {'dockchannel_await', 'dockchannel_init', 'dockchannel_recv', 'dockchannel_send'}
MODULES = {
    'phy-apple-t6050-usb2': 'phy-apple-t6050-usb2.c',
    'dwc3-apple-t6050': 'dwc3-apple-t6050.c',
    'azahi-usb-overlay': 'azahi-usb-overlay.c',
    'azahi_hpm_once': 'pd-backport/hpm-once.c',
}


def sha256(path):
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def verify_rpm(path):
    if sha256(path) != RPM_SHA256:
        raise ValueError('Wrong devel RPM checksum; no output created')


def check_module(path):
    """Basic artifact checks in addition to the real modpost export checks."""
    data = path.read_bytes()
    if (len(data) < 64 or data[:6] != b'\x7fELF\x02\x01'
            or struct.unpack_from('<HH', data, 16) != (1, 183)):
        raise ValueError(f'{path.name}: not an AArch64 ELF64 relocatable module')
    if b'vermagic=' + KERNEL.encode() + b' SMP preempt mod_unload aarch64\0' not in data:
        raise ValueError(f'{path.name}: wrong vermagic')
    sections = subprocess.check_output(['readelf', '-SW', str(path)], text=True)
    layout = re.search(r'\]\s+\.gnu\.linkonce\.this_module\s+PROGBITS\s+\S+\s+\S+\s+(\S+)', sections)
    if not layout or int(layout[1], 16) != 0x540:
        raise ValueError(f'{path.name}: wrong target module structure size')


def check_provider_exports(module, symvers, required):
    """Check the built provider, not just the kernel's preexisting exports."""
    symbols = {line.split()[-1] for line in subprocess.check_output(
               ['nm', str(module)], text=True).splitlines() if line.split()}
    exports = {fields[1] for line in symvers.read_text().splitlines()
               if len(fields := line.split()) >= 4 and Path(fields[2]).name == module.stem}
    if (required - exports or
            {'__ksymtab_' + name for name in required} - symbols):
        raise ValueError(f'{module.stem} module does not export all required symbols')


def check_nvme_core_exports(module, symvers, kernel_symvers):
    def exports(path):
        return {f[1]: f[3:] for line in path.read_text().splitlines()
                if len(f := line.split()) >= 4 and Path(f[2]).name == 'nvme-core'}

    original, actual = exports(kernel_symvers), exports(symvers)
    if (not original or set(actual) != set(original) | {NVME_CORE_MARKER}
            or any(actual[k] != v for k, v in original.items())
            or actual[NVME_CORE_MARKER] != ['EXPORT_SYMBOL_GPL']):
        raise ValueError('NVMe core exports differ from the pinned ABI and pairing marker')
    symbols = {line.split()[-1] for line in subprocess.check_output(
               ['nm', str(module)], text=True).splitlines() if line.split()}
    if {'__ksymtab_' + name for name in actual} - symbols:
        raise ValueError('The built NVMe core does not export its required symbols')


def build(args):
    rpm, output = args.devel_rpm.resolve(), args.output.absolute()
    if output.exists() or output.is_symlink():
        raise ValueError('Output exists; choose a new directory')
    verify_rpm(rpm)
    smc_source = getattr(args, 'smc_source', None)
    smc_power_source = getattr(args, 'smc_power_source', None)
    dockchannel_source = getattr(args, 'dockchannel_source', None)
    nvme_header = getattr(args, 'nvme_header', None)
    nvme_core_source = getattr(args, 'nvme_core_source', None)
    core_pins = None
    if nvme_core_source:
        core_pins = json.loads((HERE.parent / 'nvme-driver/core-source-pins.json').read_text())['sources']
        expected = {name + '.c' for name in NVME_CORE_PARTS} | {'nvme.h', 'trace.h', 'fabrics.h'}
        if set(core_pins) != expected:
            raise ValueError('Unexpected NVMe core source pin set')
        for name, expected_hash in core_pins.items():
            if sha256(nvme_core_source / name) != expected_hash:
                raise ValueError('Wrong NVMe core source checksum: ' + name)
        nvme_header = nvme_header or nvme_core_source / 'nvme.h'
        if not shutil.which('patch'):
            raise ValueError('The patch command is required for paired NVMe candidates')
    if smc_power_source and not smc_source:
        raise ValueError('The battery candidate also requires --smc-source')
    if smc_source:
        if sha256(smc_source) != SMC_SOURCE_SHA256:
            raise ValueError('Wrong macsmc.c checksum; no output created')
        if not shutil.which('patch'):
            raise ValueError('The patch command is required for the SMC candidate')
    if smc_power_source and sha256(smc_power_source) != SMC_POWER_SOURCE_SHA256:
        raise ValueError('Wrong macsmc-power.c checksum; no output created')
    if dockchannel_source:
        if sha256(dockchannel_source) != DOCKCHANNEL_SOURCE_SHA256:
            raise ValueError('Wrong dockchannel.c checksum; no output created')
        if not shutil.which('patch'):
            raise ValueError('The patch command is required for the DockChannel candidate')
    if nvme_header and sha256(nvme_header) != NVME_HEADER_SHA256:
        raise ValueError('Wrong nvme.h checksum; no output created')
    cc, ld = args.cross_prefix + 'gcc', args.cross_prefix + 'ld'
    for tool in (cc, ld, args.host_cc, args.bsdtar, args.dtc, 'readelf', 'nm'):
        if not shutil.which(tool):
            raise ValueError('Missing tool: ' + tool)
    target = subprocess.check_output([cc, '-dumpmachine'], text=True).strip()
    version = subprocess.check_output([cc, '-dumpfullversion'], text=True).strip()
    if not target.startswith('aarch64-') or not version.startswith('16.1.'):
        raise ValueError('This recipe requires AArch64 GCC 16.1; review flags for other compilers')

    output.mkdir(parents=True)
    commands = []

    def run(argv, *, input=None):
        argv = [str(arg) for arg in argv]
        commands.append(argv)
        with (output / 'commands.json').open('w') as log:
            json.dump(commands, log, indent=2)
        result = subprocess.run(argv, input=input, text=True, capture_output=True)
        with (output / 'build.log').open('a') as log:
            log.write(result.stdout + result.stderr)
        if result.returncode:
            raise RuntimeError(f'{Path(argv[0]).name} failed; see {output / "build.log"}')
        return result.stdout

    extracted = output / 'headers'
    extracted.mkdir()
    run([args.bsdtar, '-xf', rpm, '-C', extracted])
    headers = extracted / 'usr/src/kernels' / KERNEL
    if sha256(headers / '.config') != CONFIG_SHA256:
        raise ValueError('Header config differs from the recorded target')
    if sha256(headers / 'Module.symvers') != SYMVERS_SHA256:
        raise ValueError('Kernel export table differs from the pinned package')

    src = output / 'src'
    src.mkdir()
    modules = MODULES.copy()
    sources = list(modules.values()) + ['pd-backport/hpm-awake.h',
              'pd-backport/spmi4-transport.h', 'strip-symbols.py', 'mk-blob-header.py']
    sources += [str(p.relative_to(HERE)) for p in sorted((HERE / 'vendor/dwc3').glob('*.h'))]
    sources += [f'dts/t6050-j714s-usb-right-{name}.dtso' for name in ('minimal', 'pmgr')]
    source_paths = {name: HERE / name for name in sources}
    if args.with_input:
        name = 'input-driver/dockchannel-hid.c'
        modules['dockchannel-hid'] = name
        sources.append(name)
        source_paths[name] = HERE.parent / name
    if dockchannel_source:
        name = 'drivers/soc/apple/dockchannel.c'
        modules['apple-dockchannel'] = name
        sources.append(name)
        source_paths[name] = dockchannel_source
        name = 'input-driver/dockchannel-timeout.patch'
        sources.append(name)
        source_paths[name] = HERE.parent / name
    if smc_source:
        name = 'drivers/mfd/macsmc.c'
        modules['macsmc'] = name
        sources.append(name)
        source_paths[name] = smc_source
        name = 'smc-driver/sram32.patch'
        sources.append(name)
        source_paths[name] = HERE.parent / name
    if smc_power_source:
        name = 'drivers/power/supply/macsmc-power.c'
        modules['macsmc-power'] = name
        sources.append(name)
        source_paths[name] = smc_power_source
        name = 'smc-driver/power-macos27.patch'
        sources.append(name)
        source_paths[name] = HERE.parent / name
    if nvme_header:
        for module, source in (('nvme-apple', 'apple.c'), ('apple-sart', 'sart.c')):
            name = 'nvme-driver/' + source
            modules[module] = name
            sources.append(name)
            source_paths[name] = HERE.parent / name
        name = 'nvme-driver/nvme.h'
        sources.append(name)
        source_paths[name] = nvme_header
    if nvme_core_source:
        # This exact configuration enables these nine core objects.
        modules['nvme-core'] = None
        for name in core_pins:
            if name == 'nvme.h':
                continue
            source_name = 'nvme-driver/' + name
            sources.append(source_name)
            source_paths[source_name] = nvme_core_source / name
        name = 'nvme-driver/firmware-compat.patch'
        sources.append(name)
        source_paths[name] = HERE.parent / name
    for name in sources:
        dest = src / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_paths[name], dest)
    if dockchannel_source:
        run(['patch', '--batch', '--fuzz=0', '-p1', '-d', src,
             '-i', src / 'input-driver/dockchannel-timeout.patch'])
    if smc_source:
        run(['patch', '--batch', '--fuzz=0', '-p1', '-d', src,
             '-i', src / 'smc-driver/sram32.patch'])
    if smc_power_source:
        run(['patch', '--batch', '--fuzz=0', '-p1', '-d', src,
             '-i', src / 'smc-driver/power-macos27.patch'])
    if nvme_core_source:
        run(['patch', '--batch', '--fuzz=0', '-p1', '-d', src,
             '-i', src / 'nvme-driver/firmware-compat.patch'])

    for variant in ('minimal', 'pmgr'):
        name = f't6050-j714s-usb-right-{variant}'
        blob = output / (name + '.dtbo')
        symbols = output / (name + '.symbols.dtbo')
        run([args.dtc, '-q', '-@', '-I', 'dts', '-O', 'dtb',
             '-o', symbols, src / 'dts' / (name + '.dtso')])
        text = run([args.dtc, '-q', '-I', 'dtb', '-O', 'dts', symbols])
        stripped = run([sys.executable, src / 'strip-symbols.py'], input=text)
        run([args.dtc, '-q', '-I', 'dts', '-O', 'dtb', '-o', blob], input=stripped)
        checked = run([args.dtc, '-q', '-I', 'dtb', '-O', 'dts', blob])
        if '__symbols__' in checked or '__local_fixups__ {' not in checked:
            raise ValueError('Overlay symbol/fixup check failed')
    run([sys.executable, src / 'mk-blob-header.py', output / 'overlay-blobs.h',
         f'overlay_minimal={output}/t6050-j714s-usb-right-minimal.dtbo',
         f'overlay_pmgr={output}/t6050-j714s-usb-right-pmgr.dtbo'])

    # Rebuild only the host executable. Keep the RPM's target-generated offsets.
    modpost = output / 'modpost'
    run([args.host_cc, '-O2', '-I' + str(headers / 'scripts/include'),
         *(headers / 'scripts/mod' / (name + '.c')
           for name in ('modpost', 'file2alias', 'sumversion', 'symsearch')),
         '-o', modpost])
    guard = re.search(r'^#define TSK_STACK_CANARY\s+(\d+)\b',
                      (headers / 'include/generated/asm-offsets.h').read_text(), re.M)
    if not guard:
        raise ValueError('Missing target stack-canary offset')
    flags = ['-std=gnu11', '-fms-extensions', '-O2', '-g', '-nostdinc',
             f'-ffile-prefix-map={output}=.', f'-fdebug-prefix-map={Path.cwd()}=.',
             '-D__KERNEL__', '-DMODULE', '-mgeneral-regs-only', '-mno-outline-atomics',
             '-mbranch-protection=pac-ret', '-Wa,-march=armv8.5-a',
             '-DARM64_ASM_ARCH="armv8.5-a"', '-fno-pic', '-fno-pie',
             '-fno-strict-aliasing', '-fno-common', '-fshort-wchar', '-funsigned-char',
             '-fno-asynchronous-unwind-tables', '-fno-unwind-tables',
             '-fno-delete-null-pointer-checks', '-fno-strict-overflow',
             '-fno-omit-frame-pointer', '-fno-optimize-sibling-calls',
             '-fno-allow-store-data-races', '-fno-stack-clash-protection',
             '-ftrivial-auto-var-init=zero', '-fzero-init-padding-bits=all',
             '-fstrict-flex-arrays=3', '-fstack-protector-strong',
             '-mstack-protector-guard=sysreg', '-mstack-protector-guard-reg=sp_el0',
             '-mstack-protector-guard-offset=' + guard[1],
             '-Wall', '-Werror=implicit-function-declaration', '-Werror=incompatible-pointer-types']
    for directory in ('arch/arm64/include', 'arch/arm64/include/generated', 'include',
                      'arch/arm64/include/uapi', 'arch/arm64/include/generated/uapi',
                      'include/uapi', 'include/generated/uapi'):
        flags += ['-I', str(headers / directory)]
    for name in ('kconfig.h', 'compiler_types.h'):
        flags += ['-include', str(headers / 'include/linux' / name)]
    flags += ['-I', str(output), '-I', str(src / 'vendor/dwc3')]
    objects = []
    for name, source in modules.items():
        module = name.replace('-', '_')
        defines = [f'-DKBUILD_MODNAME="{module}"', f'-DKBUILD_BASENAME="{module}"',
                   f'-D__KBUILD_MODNAME=kmod_{module}']
        obj = output / (name + '.o')
        if name == 'nvme-core':
            parts = []
            for part in NVME_CORE_PARTS:
                item = output / ('nvme-core-' + part + '.o')
                original = src / 'nvme-driver' / (part + '.c')
                part_defines = [f'-DKBUILD_BASENAME="{part}"' if value.startswith('-DKBUILD_BASENAME=')
                                else value for value in defines]
                run([cc, '-I', src / 'nvme-driver', *flags, *part_defines,
                     '-MMD', '-MF', str(item) + '.d', '-c', original, '-o', item])
                dependencies = Path(str(item) + '.d').read_text().replace('\\\n', ' ').split(':', 1)[1].split()
                metadata = f'source_{item} := {original}\n' + f'deps_{item} := \\\n'
                metadata += ''.join('  ' + dep + ' \\\n' for dep in dependencies) + '\n'
                (output / ('.' + item.name + '.cmd')).write_text(metadata)
                parts.append(item)
            (output / 'nvme-core.mod').write_text(''.join(str(p) + '\n' for p in parts))
            run([ld, '-m', 'aarch64elf', '-r', '-o', obj, *parts])
        else:
            run([cc, *flags, *defines, '-c', src / source, '-o', obj])
        objects.append(obj)
    # No warning-only mode: missing exports or namespaces must fail the build.
    run([modpost, '-M', '-e', '-i', headers / 'Module.symvers',
         '-o', output / 'Module.symvers', *objects])
    common = output / 'module-common.o'
    run([cc, *flags, '-c', headers / 'scripts/module-common.c', '-o', common])
    exported = {line.split()[1] for line in (headers / 'Module.symvers').read_text().splitlines()}
    if nvme_core_source:
        exported.add(NVME_CORE_MARKER)
    for name in modules:
        module = name.replace('-', '_')
        run([cc, *flags, f'-DKBUILD_MODNAME="{module}"',
             f'-DKBUILD_BASENAME="{module}"', f'-D__KBUILD_MODNAME=kmod_{module}',
             '-c', output / (name + '.mod.c'), '-o', output / (name + '.mod.o')])
        artifact = output / (name + '.ko')
        run([ld, '-m', 'aarch64elf', '-r', '-T', headers / 'scripts/module.lds',
             '-o', artifact, output / (name + '.o'), output / (name + '.mod.o'), common])
        check_module(artifact)
        undefined = {line.split()[-1] for line in run(['nm', '-u', artifact]).splitlines()}
        if undefined - exported:
            raise ValueError(f'{artifact.name}: final linked module contains missing exports')
    if nvme_header:
        check_provider_exports(output / 'apple-sart.ko', output / 'Module.symvers', SART_EXPORTS)
    if dockchannel_source:
        check_provider_exports(output / 'apple-dockchannel.ko', output / 'Module.symvers', DOCKCHANNEL_EXPORTS)
    if nvme_core_source:
        check_nvme_core_exports(output / 'nvme-core.ko', output / 'Module.symvers', headers / 'Module.symvers')
    artifacts = [output / (name + '.ko') for name in modules]
    artifacts += [output / f't6050-j714s-usb-right-{name}.dtbo' for name in ('minimal', 'pmgr')]
    manifest = {
        'status': 'offline candidates; not installed or hardware-tested',
        'kernel': KERNEL, 'devel_rpm_sha256': RPM_SHA256,
        'modules': list(modules),
        'smc_base_sha256': SMC_SOURCE_SHA256 if smc_source else None,
        'smc_power_base_sha256': SMC_POWER_SOURCE_SHA256 if smc_power_source else None,
        'dockchannel_base_sha256': DOCKCHANNEL_SOURCE_SHA256 if dockchannel_source else None,
        'nvme_header_sha256': NVME_HEADER_SHA256 if nvme_header else None,
        'nvme_firmware_compatibility': bool(nvme_core_source),
        'nvme_core_original_sources': core_pins,
        'j714s_storage_mode': 'read-only' if nvme_header else None,
        'builder_sha256': sha256(Path(__file__)),
        'config_sha256': CONFIG_SHA256, 'kernel_symvers_sha256': SYMVERS_SHA256,
        'compiler': run([cc, '--version']).splitlines()[0],
        'limitations': ['Compiler differs from Fedora GCC 16.1.1',
                        'No module signature, BTF or ftrace instrumentation',
                        'Exact kernel disables CONFIG_MODVERSIONS',
                        'Private ADT/baseline DTB comparison not performed',
                        'Existing installation pins intentionally unchanged'],
        'sources': {name: sha256(src / name) for name in sources},
        'artifacts': {p.name: sha256(p) for p in sorted(artifacts)},
    }
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(f'Built {len(modules)} candidates with strict export checks. Manifest: {output / "manifest.json"}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--devel-rpm', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--with-input', action='store_true')
    parser.add_argument('--dockchannel-source', type=Path,
                        help='Exact kernel drivers/soc/apple/dockchannel.c; opt-in FIFO timeout fix')
    parser.add_argument('--smc-source', type=Path, help='Exact kernel drivers/mfd/macsmc.c')
    parser.add_argument('--smc-power-source', type=Path,
                        help='Exact kernel drivers/power/supply/macsmc-power.c; requires --smc-source')
    parser.add_argument('--nvme-header', type=Path,
                        help='Exact kernel drivers/nvme/host/nvme.h; builds public read-only storage')
    parser.add_argument('--nvme-core-source', type=Path,
                        help='Exact kernel drivers/nvme/host directory; opt-in paired firmware experiment')
    parser.add_argument('--cross-prefix', default='aarch64-linux-gnu-')
    parser.add_argument('--host-cc', default='gcc')
    parser.add_argument('--bsdtar', default='bsdtar')
    parser.add_argument('--dtc', default='dtc')
    args = parser.parse_args()
    try:
        build(args)
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        parser.exit(1, f'USB build failed: {error}\n')


if __name__ == '__main__':
    main()
