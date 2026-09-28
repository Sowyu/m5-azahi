#!/usr/bin/env python3
"""Refusal checks. AZAHI_USB_BUILD adds real artifact and missing-export tests."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location('builder', Path(__file__).with_name('build-linux.py'))
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)
BUILD = Path(os.environ['AZAHI_USB_BUILD']) if os.environ.get('AZAHI_USB_BUILD') else None


class BuildChecks(unittest.TestCase):
    def setUp(self):
        if not shutil.which('trash-put'):
            raise RuntimeError('Install trash-cli: sudo apt-get install -y trash-cli')
        self.root = Path(tempfile.mkdtemp(prefix='azahi-build-test-'))
        self.addCleanup(subprocess.run, ['trash-put', str(self.root)], check=True)

    def test_wrong_package_refused_before_creating_output(self):
        rpm = self.root / 'wrong.rpm'
        rpm.write_bytes(b'not the verified package')
        output = self.root / 'output'
        with self.assertRaisesRegex(ValueError, 'checksum'):
            builder.build(argparse.Namespace(devel_rpm=rpm, output=output))
        self.assertFalse(output.exists())

    def test_existing_output_preserved_before_reading_package(self):
        marker = self.root / 'marker'
        marker.write_text('keep existing build')
        with self.assertRaisesRegex(ValueError, 'Output exists'):
            builder.build(argparse.Namespace(devel_rpm=self.root / 'absent.rpm', output=self.root))
        self.assertEqual(marker.read_text(), 'keep existing build')

    def test_wrong_smc_source_refused_before_creating_output(self):
        source = self.root / 'macsmc.c'
        source.write_text('not the pinned SMC driver')
        output = self.root / 'output'
        with patch.object(builder, 'verify_rpm'):
            with self.assertRaisesRegex(ValueError, 'macsmc.c checksum'):
                builder.build(argparse.Namespace(devel_rpm=self.root / 'unused.rpm',
                              output=output, smc_source=source))
        self.assertFalse(output.exists())

    def test_dockchannel_source_and_patch_tool_required_before_creating_output(self):
        source = self.root / 'dockchannel.c'
        source.write_text('not the pinned FIFO driver')
        output = self.root / 'output'
        args = argparse.Namespace(devel_rpm=self.root / 'unused.rpm', output=output,
                                  dockchannel_source=source)
        with patch.object(builder, 'verify_rpm'):
            with self.assertRaisesRegex(ValueError, 'dockchannel.c checksum'):
                builder.build(args)
            with patch.object(builder, 'sha256', return_value=builder.DOCKCHANNEL_SOURCE_SHA256), \
                    patch.object(builder.shutil, 'which', return_value=None):
                with self.assertRaisesRegex(ValueError, 'patch command is required'):
                    builder.build(args)
        self.assertFalse(output.exists())

    def test_battery_source_and_core_pair_required_before_creating_output(self):
        output = self.root / 'output'
        args = argparse.Namespace(devel_rpm=self.root / 'unused.rpm', output=output,
                                  smc_power_source=self.root / 'power.c', smc_source=None)
        with patch.object(builder, 'verify_rpm'):
            with self.assertRaisesRegex(ValueError, 'requires --smc-source'):
                builder.build(args)
            args.smc_source = self.root / 'core.c'
            with patch.object(builder, 'sha256', side_effect=[builder.SMC_SOURCE_SHA256, 'bad']):
                with self.assertRaisesRegex(ValueError, 'macsmc-power.c checksum'):
                    builder.build(args)
        self.assertFalse(output.exists())

    def test_bad_elf_rejected(self):
        path = self.root / 'bad.ko'
        for data in (b'', b'\x7fELF\x02\x01', Path(sys.executable).read_bytes()):
            path.write_bytes(data)
            with self.assertRaises(ValueError):
                builder.check_module(path)

    def test_wrong_nvme_header_refused_before_creating_output(self):
        header = self.root / 'nvme.h'
        header.write_text('not the pinned internal NVMe header')
        output = self.root / 'output'
        with patch.object(builder, 'verify_rpm'):
            with self.assertRaisesRegex(ValueError, 'nvme.h checksum'):
                builder.build(argparse.Namespace(devel_rpm=self.root / 'unused.rpm',
                              output=output, nvme_header=header))
        self.assertFalse(output.exists())

    def test_each_nvme_core_source_is_pinned_before_creating_output(self):
        pins = json.loads((builder.HERE.parent / 'nvme-driver/core-source-pins.json').read_text())['sources']
        output = self.root / 'output'
        args = argparse.Namespace(devel_rpm=self.root / 'unused.rpm', output=output,
                                  nvme_core_source=self.root / 'source')
        for name in pins:
            with self.subTest(file=name), patch.object(builder, 'verify_rpm'), \
                    patch.object(builder, 'sha256', side_effect=lambda p: 'bad' if p.name == name else pins[p.name]):
                with self.assertRaisesRegex(ValueError, 'Wrong NVMe core source checksum: ' + name):
                    builder.build(args)
            self.assertFalse(output.exists())

    @unittest.skipUnless(BUILD and (BUILD / 'nvme-core.ko').is_file(),
                         'Needs a build with --nvme-core-source')
    def test_paired_nvme_core_exports_preserve_abi(self):
        module, symvers = BUILD / 'nvme-core.ko', BUILD / 'Module.symvers'
        kernel = BUILD / 'headers/usr/src/kernels' / builder.KERNEL / 'Module.symvers'
        builder.check_nvme_core_exports(module, symvers, kernel)
        changed = self.root / 'nvme-core.ko'
        symbol = ('__ksymtab_' + builder.NVME_CORE_MARKER).encode() + b'\0'
        self.assertIn(symbol, module.read_bytes())
        changed.write_bytes(module.read_bytes().replace(symbol, b'X' * (len(symbol) - 1) + b'\0'))
        with self.assertRaisesRegex(ValueError, 'does not export'):
            builder.check_nvme_core_exports(changed, symvers, kernel)
        table = self.root / 'wrong.symvers'
        table.write_text('\n'.join(line for line in symvers.read_text().splitlines()
                                   if builder.NVME_CORE_MARKER not in line) + '\n')
        with self.assertRaisesRegex(ValueError, 'exports differ'):
            builder.check_nvme_core_exports(module, table, kernel)
        core_row = next(line for line in symvers.read_text().splitlines()
                        if Path(line.split()[2]).name == 'nvme-core')
        table.write_text(symvers.read_text().replace(core_row, core_row.replace('EXPORT_SYMBOL_GPL', 'EXPORT_SYMBOL')))
        with self.assertRaisesRegex(ValueError, 'exports differ'):
            builder.check_nvme_core_exports(module, table, kernel)

    @unittest.skipUnless(BUILD and (BUILD / 'nvme-core.ko').is_file(),
                         'Needs a build with --nvme-core-source')
    def test_firmware_driver_requires_paired_core_before_loading(self):
        commands = json.loads((BUILD / 'commands.json').read_text())
        command = next(c for c in commands if Path(c[0]).name == 'modpost')[:]
        objects = []
        for name in ('nvme-apple.o', 'apple-sart.o'):
            target = self.root / name
            shutil.copyfile(BUILD / name, target)
            objects.append(str(target))
        command[command.index('-o') + 1] = str(self.root / 'Module.symvers')
        command = command[:command.index('-o') + 2] + objects
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(builder.NVME_CORE_MARKER, result.stderr)
        self.assertIn('undefined!', result.stderr)
        self.assertEqual(result.stderr.count('ERROR:'), 1)

    @unittest.skipUnless(BUILD and (BUILD / 'apple-sart.ko').is_file(),
                         'Needs a build with --nvme-header')
    def test_actual_sart_exports_required_in_provider_and_table(self):
        module, symvers = BUILD / 'apple-sart.ko', BUILD / 'Module.symvers'
        self.check_provider_exports(module, symvers, builder.SART_EXPORTS)

    @unittest.skipUnless(BUILD and (BUILD / 'apple-dockchannel.ko').is_file(),
                         'Needs a build with --dockchannel-source')
    def test_actual_dockchannel_exports_and_patched_source(self):
        self.check_provider_exports(BUILD / 'apple-dockchannel.ko', BUILD / 'Module.symvers',
                                    builder.DOCKCHANNEL_EXPORTS)
        manifest = json.loads((BUILD / 'manifest.json').read_text())
        self.assertEqual(manifest['dockchannel_base_sha256'], builder.DOCKCHANNEL_SOURCE_SHA256)
        source = 'drivers/soc/apple/dockchannel.c'
        self.assertEqual(builder.sha256(BUILD / 'src' / source), manifest['sources'][source])
        self.assertIn('dockchannel_cancel_wait', (BUILD / 'src' / source).read_text())
        calls = json.loads((BUILD / 'commands.json').read_text())
        self.assertTrue(any(Path(c[0]).name == 'patch' and '--fuzz=0' in c
                            and c[-1].endswith('/input-driver/dockchannel-timeout.patch') for c in calls))

    def check_provider_exports(self, module, symvers, required):
        builder.check_provider_exports(module, symvers, required)
        changed_table = self.root / 'missing.symvers'
        changed_table.write_text('')
        with self.assertRaisesRegex(ValueError, 'module does not export'):
            builder.check_provider_exports(module, changed_table, required)
        for symbol in required:
            directory = self.root / symbol
            directory.mkdir()
            changed = directory / module.name
            name = ('__ksymtab_' + symbol).encode() + b'\0'
            data = module.read_bytes()
            self.assertIn(name, data)
            changed.write_bytes(data.replace(name, b'X' * (len(name) - 1) + b'\0'))
            with self.assertRaisesRegex(ValueError, 'module does not export'):
                builder.check_provider_exports(changed, symvers, required)

    @unittest.skipUnless(BUILD, 'Set AZAHI_USB_BUILD to an offline build directory')
    def test_real_artifacts_and_mutated_release(self):
        manifest = json.loads((BUILD / 'manifest.json').read_text())
        for name in manifest.get('modules', builder.MODULES):
            path = BUILD / (name + '.ko')
            builder.check_module(path)
            self.assertEqual(builder.sha256(path), manifest['artifacts'][path.name])
            changed = self.root / path.name
            changed.write_bytes(path.read_bytes().replace(builder.KERNEL.encode(), b'X' * len(builder.KERNEL)))
            with self.assertRaisesRegex(ValueError, 'vermagic'):
                builder.check_module(changed)

    @unittest.skipUnless(BUILD, 'Set AZAHI_USB_BUILD to an offline build directory')
    def test_missing_module_structure_is_rejected(self):
        path = BUILD / 'azahi_hpm_once.ko'
        changed = self.root / path.name
        data = path.read_bytes()
        section = b'.gnu.linkonce.this_module\0'
        self.assertIn(section, data)
        changed.write_bytes(data.replace(section, b'X' * (len(section) - 1) + b'\0'))
        with self.assertRaisesRegex(ValueError, 'module structure'):
            builder.check_module(changed)

    @unittest.skipUnless(BUILD, 'Set AZAHI_USB_BUILD to an offline build directory')
    def test_actual_modpost_rejects_missing_exports(self):
        commands = json.loads((BUILD / 'commands.json').read_text())
        original = next(command for command in commands if Path(command[0]).name == 'modpost')
        self.assertNotIn('-w', original)
        obj = self.root / 'azahi_hpm_once.o'
        shutil.copyfile(BUILD / obj.name, obj)
        symbols = self.root / 'empty.symvers'
        symbols.write_text('')
        command = original[:]
        command[command.index('-i') + 1] = str(symbols)
        command[command.index('-o') + 1] = str(self.root / 'Module.symvers')
        command = command[:command.index('-o') + 2] + [str(obj)]
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('undefined!', result.stderr)

    @unittest.skipUnless(BUILD and all(shutil.which(t) for t in ('cpp', 'dtc', 'fdtoverlay', 'fdtget')),
                         'Needs AZAHI_USB_BUILD and device-tree tools')
    def test_overlays_merge_and_resolve_local_references(self):
        source = Path(__file__).resolve().parents[1] / 'research-archive/t6050-j714s-native-rootguard.dts'
        pre, base = self.root / 'base.dts', self.root / 'base.dtb'
        subprocess.run(['cpp', '-nostdinc', '-undef', '-D__DTS__', '-x', 'assembler-with-cpp',
                        '-I', str(source.parent), str(source), '-o', str(pre)], check=True)
        # No -@: the installed tree also lacks /__symbols__.
        subprocess.run(['dtc', '-q', '-I', 'dts', '-O', 'dtb', '-o', str(base), str(pre)], check=True)

        def cells(blob, node, prop):
            text = subprocess.check_output(['fdtget', '-t', 'x', str(blob), node, prop], text=True)
            return [int(v, 16) for v in text.split()]

        aic = '/soc/interrupt-controller@280400000'
        original_aic = cells(base, aic, 'phandle')
        for variant in ('minimal', 'pmgr'):
            with self.subTest(variant=variant):
                overlay = BUILD / f't6050-j714s-usb-right-{variant}.dtbo'
                merged = self.root / f'merged-{variant}.dtb'
                subprocess.run(['fdtoverlay', '-i', str(base), '-o', str(merged), str(overlay)], check=True)
                usb = '/soc/usb@382280000'
                phy = cells(merged, '/soc/phy@382a90000', 'phandle')[0]
                dart0 = cells(merged, '/soc/iommu@382f00000', 'phandle')[0]
                dart1 = cells(merged, '/soc/iommu@382f80000', 'phandle')[0]
                self.assertEqual(cells(merged, aic, 'phandle'), original_aic)
                self.assertEqual(cells(merged, usb, 'interrupt-parent'), original_aic)
                self.assertEqual(cells(merged, usb, 'phys'), [phy, 3])
                self.assertEqual(cells(merged, usb, 'iommus'), [dart0, 0, dart0, 1, dart1, 0, dart1, 1])
                self.assertEqual(len({phy, dart0, dart1, *original_aic}), 4)


if __name__ == '__main__':
    unittest.main()
