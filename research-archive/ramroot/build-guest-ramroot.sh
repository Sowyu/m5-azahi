#!/bin/sh
# build-guest-ramroot.sh - produce guest-hv-ramroot.bin: an m1n1-hv guest image
# whose initramfs carries an entire Fedora root filesystem, run from RAM.
#
#   sh ramroot/build-guest-ramroot.sh [ROOT_IMG]
#
# ROOT_IMG defaults to root.img extracted from fedora-minimal.zip (btrfs,
# Fedora Minimal, 1.28 GB used).  Pass the KDE image's root.img for the KDE
# stage.  Output: guest-hv-ramroot.bin in the project root + sha256.
#
# Image layout produced (all offsets discovered from the PROVEN-BOOTING
# guest-hv-initrd.bin, not rebuilt from possibly-drifted parts):
#   [guest m1n1][chosen.bootargs=...\n][dtb][Image.gz][m1n1_initramfs][le32]
#   [initramfs-asahi.img (zstd) ++ ramroot.cpio.zst (zstd)]
# The kernel unpacks concatenated zstd cpio streams; the second overlays the
# first.  m1n1's size field is le32: the combined blob MUST stay < 4 GiB
# (asserted).  If a KDE blob exceeds it, patch payload.c to a u64 size first.
set -e
D="$(cd "$(dirname "$0")/.." && pwd)"
R="$D/ramroot"
# WORK/OUTNAME overridable so the KDE build does not clobber the minimal one
WORK="${WORK:-$R/work}"
OUTNAME="${OUTNAME:-guest-hv-ramroot.bin}"
mkdir -p "$WORK"

ROOT_IMG="${1:-$WORK/root.img}"
if [ ! -f "$ROOT_IMG" ]; then
    echo "=== extracting root.img from fedora-minimal.zip (3.9 GB) ==="
    unzip -o "$D/fedora-minimal.zip" root.img -d "$WORK"
fi

# SKIP_CPIO=1: reuse work/ramroot.cpio.zst (rebuild only bootargs/dtb/assembly)
if [ "${SKIP_CPIO:-0}" = "1" ] && [ -f "$WORK/ramroot.cpio.zst" ]; then
    echo "=== reusing existing $WORK/ramroot.cpio.zst ==="
else

echo "=== building overlay tree ==="
OVL="$WORK/sysroot-overlay"
rm -rf "$OVL"
# autologin root on tty1: gives logind a seat0+VT session (required for any
# Wayland compositor later); harmless bash login on the minimal image
mkdir -p "$OVL/etc/systemd/system/getty@tty1.service.d"
cat > "$OVL/etc/systemd/system/getty@tty1.service.d/autologin.conf" <<'EOF'
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin root --noclear %I $TERM
EOF
# autologin root on the SERIAL console too. The vuart (ttySAC0) is how the
# host drives this machine; without this the boot ends at "fedora login:" and
# the image ships no known root password, so it is unreachable from the host.
mkdir -p "$OVL/etc/systemd/system/serial-getty@ttySAC0.service.d"
cat > "$OVL/etc/systemd/system/serial-getty@ttySAC0.service.d/autologin.conf" <<'EOF'
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin root --noclear %I $TERM
EOF
mkdir -p "$OVL/root"
cat > "$OVL/root/.bash_profile" <<'EOF'
# On the seat0 VT: start Plasma if this rootfs has it (KDE stage only).
if [ "$(tty)" = "/dev/tty1" ] && command -v startplasma-wayland >/dev/null; then
    export QT_QUICK_BACKEND=software LIBGL_ALWAYS_SOFTWARE=1
    exec dbus-run-session startplasma-wayland >/var/log/plasma.log 2>&1
fi
EOF
# Start the synthetic input device at boot. The M5's real keyboard/trackpad
# hang off the MTP coprocessor over dockchannel (see BRINGUP.md) which is not
# brought up yet; uinject creates a /dev/uinput keyboard+mouse instead, which
# udev puts on seat0 and libinput/kwin treat as real hardware. Commands are
# fed to /run/uinject.fifo from the vuart shell.
mkdir -p "$OVL/etc/systemd/system/multi-user.target.wants"
cat > "$OVL/etc/systemd/system/uinject.service" <<'EOF'
[Unit]
Description=Synthetic keyboard/mouse fed from the m1n1 vuart
After=systemd-udevd.service
Before=graphical.target

[Service]
Type=simple
ExecStartPre=-/sbin/modprobe uinput
ExecStart=/usr/local/bin/uinject
Restart=on-failure
RestartSec=2

[Install]
WantedBy=multi-user.target
EOF
ln -sf ../uinject.service "$OVL/etc/systemd/system/multi-user.target.wants/uinject.service"
mkdir -p "$OVL/etc/modules-load.d"
echo uinput > "$OVL/etc/modules-load.d/uinput.conf"
mkdir -p "$OVL/usr/local/bin"
cp "$R/uinject.py" "$OVL/usr/local/bin/uinject"
chmod +x "$OVL/usr/local/bin/uinject"

echo "=== writing cpio manifest ==="
M="$WORK/manifest.txt"
: > "$M"
echo "exec /ramroot-setup.sh $R/ramroot-setup.sh" >> "$M"
echo "file /etc/systemd/system/ramroot.service $R/ramroot.service" >> "$M"
echo "slink /etc/systemd/system/initrd-root-fs.target.wants/ramroot.service ../ramroot.service" >> "$M"
# root image: whole file if < 4064 MiB, else 3072 MiB chunks
SZ=$(stat -f%z "$ROOT_IMG")
if [ "$SZ" -lt 4261412864 ]; then
    echo "file /ramroot/root.img $ROOT_IMG" >> "$M"
else
    echo "split /ramroot/root.img $ROOT_IMG 3072" >> "$M"
fi
# overlay tree
(cd "$OVL" && find . -type d | sed 's|^\.||' | grep -v '^$' | \
    while read -r p; do echo "dir /ramroot/sysroot-overlay$p"; done) >> "$M"
(cd "$OVL" && find . -type f | sed 's|^\.||' | \
    while read -r p; do echo "file /ramroot/sysroot-overlay$p $OVL$p" ; done) >> "$M"

echo "=== building ramroot.cpio (streamed, uid/gid forced to 0) ==="
python3 "$R/mkcpio.py" "$M" "$WORK/ramroot.cpio"

echo "=== compressing (zstd -T0 -12) ==="
zstd -f -T0 -12 "$WORK/ramroot.cpio" -o "$WORK/ramroot.cpio.zst"
rm -f "$WORK/ramroot.cpio"
fi # SKIP_CPIO

echo "=== assembling guest image ==="
python3 - "$D" "$WORK" <<'EOF'
import sys, os, hashlib
D, WORK = sys.argv[1], sys.argv[2]
base = open(f"{D}/guest-hv-initrd.bin", "rb").read(64 << 20)  # head only
# locate the pieces inside the proven image
b0 = base.find(b"chosen.bootargs=")
assert b0 > 0
b1 = base.index(b"\n", b0) + 1
magic = b"m1n1_initramfs"
m0 = base.find(magic, b1)
assert m0 > 0, "no initramfs payload in guest-hv-initrd.bin?"
head = base[:b0]            # guest m1n1
# swap in the CURRENT dtb: mid = fresh dtb + Image.gz slice.
# DTB=<name> selects a variant (e.g. t6050-j714s-hv-nvme.dtb, which adds the
# ANS/NVMe stack); default stays the proven RAM-only tree.
gz = base.find(b"\x1f\x8b\x08", b1, m0)
assert gz > 0, "gzip kernel not found after dtb"
dtb = os.environ.get("DTB", "t6050-j714s-hv.dtb")
print("dtb:", dtb)
mid = open(f"{D}/{dtb}", "rb").read() + base[gz:m0]
old_args = base[b0:b1 - 1].decode().split("=", 1)[1]

extra = ("root=/dev/loop0 rootfstype=btrfs rw selinux=0 plymouth.enable=0 "
         "modprobe.blacklist=pinctrl_apple_gpio "
         "systemd.mask=boot.mount systemd.mask=boot-efi.mount "
         "systemd.mask=initial-setup.service")
args = old_args + " " + extra
print("bootargs:", args)

blob = open(f"{D}/initramfs-asahi.img", "rb").read() + \
       open(f"{WORK}/ramroot.cpio.zst", "rb").read()
assert len(blob) < 0xFFFFFFFF, f"blob {len(blob)} exceeds m1n1 le32 payload size"

out = f"{D}/" + os.environ.get("OUTNAME", "guest-hv-ramroot.bin")
with open(out, "wb") as f:
    f.write(head)
    f.write(b"chosen.bootargs=" + args.encode() + b"\n")
    f.write(mid)
    f.write(magic + len(blob).to_bytes(4, "little"))
    f.write(blob)
sz = os.path.getsize(out)
h = hashlib.sha256(open(out, "rb").read()).hexdigest()
print(f"{out}: {sz} bytes ({sz/2**20:.1f} MiB)  sha256 {h[:16]}...")
if sz > 1_600_000_000:
    print("WARNING: guest image > 1.5 GiB loads at heap_top into iBoot-declared")
    print("regions whose SPTM protection status is UNPROVEN. Test load first.")
EOF

echo "=== done. deploy: cp guest-hv-ramroot.bin ~/azahi/ then"
echo "    GUEST=~/azahi/guest-hv-ramroot.bin sh ~/azahi/hv.sh"
