#!/usr/bin/env python3
"""Apply the startup patch and cross-compile it without accessing a Mac.

Also compiles the standalone caller and its read-only PMGR lookup dependency.
Keeps all outputs. Produces object files and a manifest, not a boot image.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess


ROOT = Path(__file__).resolve().parent.parent
PMGR_INPUTS = {
    'src/pmgr.c': '2dd6bcb7a3a980375f8cf05663827ac470e5091c2349586cde0fa5f702a3b546',
    'src/pmgr.h': '5719c4ed311ea6088a5bea5be95a0ac051073677ee5bcf58c9b7eb410df26a78',
}


def build(headers, output, compiler):
    headers = headers.resolve()
    output = output.resolve()
    for name in ('src/smp.h', 'src/utils.h', 'sysinc/limits.h'):
        if not (headers / name).is_file():
            raise ValueError(f'Missing m1n1 header: {headers / name}')
    if output.exists():
        raise ValueError(f'Output already exists; choose a new directory: {output}')
    target = subprocess.check_output([compiler, '-dumpmachine'], text=True).strip()
    if not target.startswith('aarch64-'):
        raise ValueError(f'An AArch64 cross compiler is required, got {target}')
    for name, expected in PMGR_INPUTS.items():
        if hashlib.sha256((headers / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f'PMGR source differs from the reviewed base: {name}')
    include = subprocess.check_output(
        [compiler, '-print-file-name=include'], text=True).strip()
    version = subprocess.check_output([compiler, '--version'], text=True).splitlines()[0]
    for tool in ('patch', 'nm'):
        if not shutil.which(tool):
            raise ValueError(f'The {tool} command is required')

    output.mkdir(parents=True)
    (output / 'src').mkdir()
    base = ROOT / 'research-archive/standalone-loader/m1n1-20260911'
    for name in ('Makefile', 'src/smp.c'):
        shutil.copyfile(base / name, output / name)
    patch = ROOT / 'smp/t6050-start-guards.patch'
    subprocess.run(['patch', '--batch', '--fuzz=0', '-p1', '-d', str(output),
                    '-i', str(patch)], check=True)
    for name in PMGR_INPUTS:
        shutil.copyfile(headers / name, output / name)
    pmgr_patch = ROOT / 'standalone-loader/pmgr-lookup.patch'
    subprocess.run(['patch', '--batch', '--fuzz=0', '-p1', '-d', str(output),
                    '-i', str(pmgr_patch)], check=True)
    for name in ('azahi_smp.c', 'azahi_smp.h', 'azahi_standalone.c', 'azahi_standalone.h'):
        shutil.copyfile(ROOT / 'standalone-loader/m1n1-20260911/src' / name,
                        output / 'src' / name)

    flags = ['-std=gnu11', '-O2', '-ffreestanding', '-fno-builtin', '-fpic',
             '-fno-stack-protector', '-nostdinc', '-isystem', include,
             '-isystem', str(headers / 'sysinc'), '-I', str(output / 'src'),
             '-I', str(headers / 'src'),
             '-mgeneral-regs-only', '-march=armv8.2-a', '-mstrict-align',
             '-Wall', '-Wextra', '-Werror']
    commands = []
    for name in ('smp', 'azahi_smp', 'pmgr', 'azahi_standalone'):
        command = [compiler, *flags, '-c', str(output / 'src' / f'{name}.c'),
                   '-o', str(output / f'{name}.o')]
        subprocess.run(command, check=True)
        commands.append(command)

    combined = output / 'loader-components.o'
    command = [compiler, '-nostdlib', '-no-pie', '-r', '-o', str(combined),
               *(str(output / (name + '.o')) for name in
                 ('smp', 'azahi_smp', 'pmgr', 'azahi_standalone'))]
    subprocess.run(command, check=True)
    commands.append(command)
    symbols = subprocess.check_output(['nm', str(combined)], text=True)
    for name in ('azahi_standalone_run', 'azahi_smp_diag', 'pmgr_lookup_device_addr'):
        if not any(line.split()[-2:] == ['T', name] for line in symbols.splitlines()):
            raise ValueError(f'Component link did not resolve {name}')

    files = [patch, pmgr_patch, combined, *(output / name for name in PMGR_INPUTS),
             *(output / 'src' / name for name in
               ('smp.c', 'azahi_smp.c', 'azahi_smp.h', 'azahi_standalone.c', 'azahi_standalone.h')),
             *(output / (name + '.o') for name in ('smp', 'azahi_smp', 'pmgr', 'azahi_standalone'))]
    manifest = {
        'status': 'cross-compiled objects only; hardware startup unresolved',
        'default_secondary_start': False,
        'pmgr_base_sha256': PMGR_INPUTS,
        'compiler': version,
        'target': target,
        'commands': commands,
        'sha256': {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
    }
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(f'Compiled and combined four loader objects. Manifest: {output / "manifest.json"}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--m1n1', required=True, type=Path, help='Complete local m1n1 header tree')
    parser.add_argument('--output', required=True, type=Path, help='New directory, kept after build')
    parser.add_argument('--cc', default='aarch64-linux-gnu-gcc', help='AArch64 GCC executable')
    args = parser.parse_args()
    try:
        build(args.m1n1, args.output, args.cc)
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f'Offline build failed: {exc}\n')


if __name__ == '__main__':
    main()
