#!/usr/bin/env python3
"""Build a small USB-loaded native kernel/initrd with actual SSD root.

No RAM filesystem image; no target/loader installation by this host builder.
"""
import hashlib
import io
import json
import lzma
from pathlib import Path
import stat
import struct
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / 'native-ssdroot-v3-20260906.bin'
RELEASE = '7.0.13-400.asahi.fc44.aarch64+16k'


def digest(path):
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def entries(data):
    """Read concatenated newc archives for inspection (never extract paths)."""
    pos = 0
    while pos < len(data):
        while pos < len(data) and data[pos] == 0:
            pos += 1
        if pos == len(data):
            break
        h = data[pos:pos + 110]
        assert h[:6] == b'070701'
        f = [int(h[i:i + 8], 16) for i in range(6, 110, 8)]
        name = data[pos + 110:pos + 110 + f[11] - 1].decode()
        pos = (pos + 110 + f[11] + 3) & ~3
        payload = data[pos:pos + f[6]]
        assert len(payload) == f[6]
        pos = (pos + f[6] + 3) & ~3
        assert not name.startswith('/') and '..' not in name.split('/')
        if name != 'TRAILER!!!':
            yield name, f[1], payload


def unpack(data):
    return subprocess.run(['zstd', '-dq', '-c'], input=data, capture_output=True, check=True).stdout


def main():
    assert not OUTPUT.exists() and not OUTPUT.with_suffix('.json').exists()
    source_path = ROOT / 'native-input-v2-20260906.bin'
    assert digest(source_path) == '538512bd3cb93e53b595dd224719e7a396b7990c51b2b10e916dff738ca4be12'
    stock = (ROOT / 'initramfs-asahi.img').read_bytes()
    minimal = ROOT / 'ramroot/work/ramroot.cpio.zst'
    with source_path.open('rb') as source:
        head = source.read(64 << 20)
        arg_start = head.index(b'chosen.bootargs=')
        dt_start = head.index(b'\n', arg_start) + 1
        kernel_start = dt_start + struct.unpack_from('>I', head, dt_start + 4)[0]
        marker = head.index(b'm1n1_initramfs', kernel_start)
        initrd_start = marker + len(b'm1n1_initramfs') + 4
        source.seek(initrd_start)
        assert source.read(len(stock)) == stock
        with minimal.open('rb') as ram:
            while chunk := ram.read(4 << 20):
                assert source.read(len(chunk)) == chunk
        overlays = source.read()
        assert 0 < len(overlays) < 4 << 20
    old_assets = {name: (mode, data) for name, mode, data in entries(unpack(overlays))}
    assert not any(name.startswith('ramroot/root.img') or name.endswith('ramroot.service') for name in old_assets)
    # Stock contents inspection catches hidden forced-root configuration.
    stock_assets = {name: (mode, data) for name, mode, data in entries(unpack(stock))}
    stock_cmdline = {name: data.decode() for name, (mode, data) in stock_assets.items()
                     if name.startswith('etc/cmdline.d/') and stat.S_ISREG(mode)}
    print('STOCK_INITRD_CMDLINE', stock_cmdline)
    dtb = (ROOT / 't6050-j714s-native-rootguard.dtb').read_bytes()
    assert hashlib.sha256(dtb).hexdigest() == 'ddd855503c88b8b3b0afe64b4f3862dee2ec328c347b6c7eca5664bdf1fee5f8'
    sys.path.insert(0, str(ROOT / 'ramroot'))
    from mkcpio import Writer, ensure_parents
    buf = io.BytesIO()
    w = Writer(buf)
    seen = set()
    assets = {}
    links = {}
    overlay_prefix = 'ramroot/sysroot-overlay/'
    root_files = {name[len(overlay_prefix):] for name, (mode, data) in old_assets.items()
                  if name.startswith(overlay_prefix) and not stat.S_ISDIR(mode)}

    def add(name, source, mode=0o644):
        ensure_parents(w, name, seen)
        w.file(name, source, mode)
        assets[name] = digest(source)
        if name.startswith(overlay_prefix):
            root_files.add(name[len(overlay_prefix):])

    def link(name, dest):
        ensure_parents(w, name, seen)
        w.symlink(name, dest)
        links[name] = dest
        if name.startswith(overlay_prefix):
            root_files.add(name[len(overlay_prefix):])

    with tempfile.TemporaryDirectory(prefix='azahi-ssdroot-build-') as temporary:
        temp = Path(temporary)
        busybox = ROOT / 'probe/vendor/ssdboot/bin/busybox.static'
        assert digest(busybox) == '198f6f675a49ac734082e054b823d3e2e947180ca2f632852ae1c09e950fd676'
        data = busybox.read_bytes()
        assert data[:4] == b'\x7fELF' and struct.unpack_from('<H', data, 18)[0] == 183
        for applet in (b'blockdev\0', b'dd\0', b'sha256sum\0', b'sync\0'):
            assert applet in data
        add('usr/local/libexec/busybox.static', busybox, 0o755)
        module_hashes = {}
        for name, directory, subpath, expected in (
            ('nvme-apple', 'build-rootguard', 'nvme/host', '696d0fded6a47bb9929e1f49b1a38d166d6c539e573696c3c206b84c13c6708c'),
            ('apple-sart', 'build', 'soc/apple', '58ba58e4a6dd0b4574751d224772d9bfe447fa3f4e8bdba8cfa9e7c52b80305d'),
        ):
            module = ROOT / 'nvme-driver' / directory / (name + '.ko')
            assert digest(module) == expected
            module_hashes[name] = expected
            packed = temp / (name + '.ko.xz')
            packed.write_bytes(lzma.compress(module.read_bytes(), check=lzma.CHECK_CRC32))
            path = f'usr/lib/modules/{RELEASE}/kernel/drivers/{subpath}/{name}.ko.xz'
            for prefix in ('', overlay_prefix):
                add(prefix + path, packed)
        for path, local in (
            ('ssdroot-prepare.sh', 'ssdroot-prepare.sh'),
            ('ssdroot-configure.sh', 'ssdroot-configure.sh'),
            ('etc/systemd/system/ssdroot-prepare.service', 'ssdroot-prepare.service'),
            ('etc/systemd/system/sysroot.mount', 'ssdroot-sysroot.mount'),
            ('etc/systemd/system/ssdroot-configure.service', 'ssdroot-configure.service'),
            ('ssdroot-run-stage.sh', 'ssdroot-run-stage.sh'),
            ('ssdroot-handoff-report.sh', 'ssdroot-handoff-report.sh'),
            ('ssdroot-emergency.sh', 'ssdroot-emergency.sh'),
            ('etc/systemd/system/emergency.service', 'ssdroot-emergency.service'),
            ('etc/systemd/system/ssdroot-prepare.service.d/diagnostic.conf', 'ssdroot-prepare-diagnostic.conf'),
            ('etc/systemd/system/ssdroot-configure.service.d/diagnostic.conf', 'ssdroot-configure-diagnostic.conf'),
            ('etc/systemd/system/initrd-switch-root.service.d/diagnostic.conf', 'ssdroot-handoff-diagnostic.conf'),
        ):
            add(path, ROOT / 'probe' / local)
        link('etc/systemd/system/initrd-root-fs.target.requires/sysroot.mount', '../sysroot.mount')
        link('etc/systemd/system/initrd-root-fs.target.requires/ssdroot-configure.service', '../ssdroot-configure.service')
        # Our explicit mount owns /sysroot; disable the dracut shell mount path
        # so it cannot race preflight or mount from stale stock assumptions.
        for unit in ('dracut-mount.service', 'dracut-initqueue.service'):
            link('etc/systemd/system/' + unit, '/dev/null')
        for path, local in (
            ('etc/fstab', 'ssdroot-fstab'),
            ('root/.bash_profile', 'native-ssd-profile.sh'),
            ('usr/local/bin/native-ssd-kde-start', 'native-ssd-kde-start.sh'),
            ('usr/local/bin/basic-kde-session', 'basic-kde-session.sh'),
            ('usr/local/bin/native-input-check', 'native-ssd-input-check.sh'),
            ('mnt/inputfiles/bringup-20260906/basic-kde-clients.sh', 'basic-kde-clients.sh'),
        ):
            add(overlay_prefix + path, ROOT / 'probe' / local, 0o755 if path.startswith('usr/local/bin/') else 0o644)
        add(overlay_prefix + 'etc/systemd/system/getty@tty1.service.d/autologin.conf',
            ROOT / 'ramroot/work/sysroot-overlay/etc/systemd/system/getty@tty1.service.d/autologin.conf')
        # Runtime masks are also in bootargs; persistent masks cover later
        # desktop starts while standalone boot is still being developed.
        for unit in ('boot.mount', 'boot-efi.mount', 'systemd-repart.service', 'systemd-repart.socket',
                     'udisks2.service', 'fstrim.service', 'fstrim.timer', 'initial-setup.service',
                     'initial-setup-graphical.service', 'uinject.service'):
            link(overlay_prefix + 'etc/systemd/system/' + unit, '/dev/null')
        listing = temp / 'overlay-files'
        listing.write_text('\n'.join(sorted(root_files)) + '\n')
        add('ssdroot-overlay-files', listing)
        w.trailer()
    extra = subprocess.run(['zstd', '-q', '-c'], input=buf.getvalue(), capture_output=True, check=True).stdout
    initrd = stock + overlays + extra
    assert len(initrd) < 100 << 20
    final_assets = dict(stock_assets)
    final_assets.update(old_assets)
    final_assets.update({name: (mode, data) for name, mode, data in entries(buf.getvalue())})
    assert not any(name.startswith('ramroot/root.img') or name.endswith('/ramroot.service') for name in final_assets)
    for path in ('usr/lib/firmware/apple/tpmtfw-j714s.bin',
                 f'usr/lib/modules/{RELEASE}/kernel/drivers/hid/dockchannel-hid/dockchannel-hid.ko.xz'):
        assert path in old_assets and final_assets[path] == old_assets[path]
    bootargs = head[arg_start:dt_start - 1].decode().split('=', 1)[1]
    bootargs = bootargs.replace('root=/dev/loop0', 'root=PARTUUID=PRIVATE-UUID-REMOVED')
    # Keep kernel messages in the journal/ring buffer, but stop informational
    # RTKit spam obscuring the much more important boot-stage error on panel.
    bootargs = ' '.join(token for token in bootargs.split() if token != 'ignore_loglevel')
    bootargs += (' rootflags=subvol=root,nodiscard azahi.ssd_root=1 systemd.unit=multi-user.target'
                 ' rd.systemd.mask=dracut-mount.service rd.systemd.mask=dracut-initqueue.service'
                 ' systemd.mask=home.mount systemd.mask=systemd-repart.service systemd.mask=systemd-repart.socket'
                 ' systemd.mask=initial-setup-graphical.service systemd.mask=uinject.service'
                 ' systemd.mask=fstrim.service systemd.mask=fstrim.timer'
                 ' module_blacklist=macsmc_power,macsmc_input,macsmc_hwmon,rtc_macsmc')
    bootargs += ' loglevel=3 azahi.ssd_diagnostics=2'
    header = head[:arg_start] + b'chosen.bootargs=' + bootargs.encode() + b'\n' + dtb + head[kernel_start:marker]
    header += b'm1n1_initramfs' + struct.pack('<I', len(initrd))
    with OUTPUT.open('xb') as dest:
        dest.write(header)
        dest.write(initrd)
    receipt = dict(image_sha256=digest(OUTPUT), dtb_sha256=hashlib.sha256(dtb).hexdigest(),
                   ssd_root=True, ram_root_image=False, initrd_bytes=len(initrd), diagnostic_console=2,
                   udev_lifetime_fix=True,
                   stock_initrd_sha256=hashlib.sha256(stock).hexdigest(),
                   input_overlays_sha256=hashlib.sha256(overlays).hexdigest(),
                   modules=module_hashes, assets=assets, links=links, root_files=sorted(root_files))
    with OUTPUT.with_suffix('.json').open('x') as output:
        json.dump(receipt, output, indent=2)
    print('SSDROOT_CANDIDATE_BUILT', OUTPUT.stat().st_size, receipt['image_sha256'], 'initrd', len(initrd))


if __name__ == '__main__':
    main()
