# Native RAM boot bring-up — 2026-09-06

**Current-state override:** native SSD-root v3 now reaches KDE; the RAM-only
state below is historical. Kernel/initramfs still arrive over USB, so
standalone startup is not available. See [current handoff](../CURRENT-STATE.md)
and [SSD-root boot checkpoint](SSDROOT-BOOT-CHECKPOINT.md) before booting.

Native Linux is now past the old pre-userspace hang. This is RAM loading over
USB followed by Linux running without the hypervisor, not an SSD install or
power-on untethered boot. Only CPU 0 is enabled. GPU rendering remains software.

## Images and checks

- `Image-asahi`: untouched stock kernel, SHA256
  `f1672f680082c40b8f606b5acd70f9a5ec7cef0d04abc2f63a2d26862a045999`.
- `Image-baremetal.bin`: existing four-NOP native candidate, SHA256
  `d2ec67ab79aea96292869f66e83c50d0fdb354d237d9787a9d6c238f0b7bffe7`.
  `verify-native-candidate.py` verifies the exact complete-image delta.
- `native-loader-prefix-20260906.bin`: unchanged prefix extracted from the
  successfully booted minimal native image. SHA256
  `ecffcf08622e64ad616d7b4e4bd6050cca44c9647df311ffb20efcc8f792a604`.
  No m1n1 source or code bytes were changed. Do not substitute the input
  guest's different loader prefix.
- `native-input-v2-20260906.bin`: 1,027,610,089 bytes, SHA256
  `538512bd3cb93e53b595dd224719e7a396b7990c51b2b10e916dff738ca4be12`.
  Native input DT, verified firmware/module/RAM-root archive, console-check
  service. **Use only the corrected boot-native.py**, which restores the
  required SMC blacklist omitted from this image's embedded boot arguments.
- `native-kde-20260906.bin`: 4,240,301,313 bytes, SHA256
  `0a03fd229096ebd0cedf0399f316c20dc50f6f4d5858a85ed0ee299890423fc5`.
  Offline validation and native graphical boot passed: systemd, Plasma
  splash, then Plasma first-run setup. Normal desktop completion and native
  physical input remain unverified; PRIVATE-USER reports severe lag.
  Initrd size 4,218,349,177 bytes (below the 32-bit payload limit). Existing
  14 GB KDE root image is chunked inside the cpio; the RAM-root setup joins
  chunks in its own tmpfs. Input overlays are preserved byte-for-byte.

## Safe native boot sequence

Requires a fresh physical restart into "Running proxy", no guest/client
active. Do not use the old hv-fixed/gstop scripts. Do not chainload a whole
1–4 GB image: the extra compressed staging allocation runs out of heap.

```sh
python3 probe/boot-native.py native-input-v2-20260906.bin --offline
sh /PRIVATE-USER/azahi/run.sh /PRIVATE-USER/azahi/proxyclient/tools/chainload.py -r /PRIVATE-USER/azahi-port/native-loader-prefix-20260906.bin
python3 -u probe/boot-native.py native-input-v2-20260906.bin
```

Choose new log paths for each run. The loader transfers directly to the
established RAM fence: kernel `0x10800000000`, FDT `0x10900000000`, initrd
`0x10a00000000`. It applies only the known MTP access filter, sets WFE before
the existing bounded SMP startup, and uses existing kboot APIs. Every chunk
uses the proxy's checked transfer plus a tail readback. No register scans,
NVMe calls, target filesystem operations or loader patches are involved.

Successful handoff closes USB; no vuart exists natively. Do not treat the
missing USB device as proof of a crash. Use the panel/webcam. Booting another
image subsequently requires a physical cycle.

Required kernel blacklist (SMC core/GPIO remain available for input):
`module_blacklist=macsmc_power,macsmc_input,macsmc_hwmon,rtc_macsmc`.
Keep existing pinctrl exclusions and absent SSD nodes too.

## Results so far

1. Minimal native stock-initramfs image reached visible kernel/systemd
   userspace boot output: `logs/native-probe-screen2-20260906.jpg`.
2. Initial fuller native input boot panicked in `macsmc_power_probe` because
   the native argument rebuild dropped the known SMC blacklist. QR crash
   capture isolated this introduced regression; it is not a new input
   transport failure. Trace:
   `logs/native-input-panic-qr3-20260906.txt` and
   `logs/native-input-panic-zxing-20260906.txt`.
3. Corrected boot passed that point and reached Fedora's automatic root
   login on the physical panel: `logs/native-input-fixed-20260906.log`,
   `logs/native-input-fixed-screen2-20260906.jpg`. Physical typing confirmation
   is still pending. Do not claim native keyboard/trackpad verification yet.
4. Native KDE reached graphical first-run setup, confirmed by PRIVATE-USER:
   `logs/native-kde-boot-20260906.log`,
   `logs/native-kde-screen4-20260906.jpg`. This supersedes earlier untested
   notes. Current priority is all CPU cores, then persistent internal boot,
   GPU later. No SSD write or installation occurred. Leave setup running
   until a specific next hardware test requires a physical restart.

## Optical crash logs

The kernel has DRM panic configured to a generic user screen. The native
runner defaults to `drm.panic_screen=qr_code` instead. Its empty compiled URL
means the code holds raw kernel log text, not a site to open.

```sh
/opt/homebrew/bin/imagesnap -w 1 logs/NEW-PHOTO.jpg
swift probe/read-panic-qr.swift logs/NEW-PHOTO.jpg
```

Vision decoded the full 40-version QR after analysis-only perspective and
contrast normalization. ZXing also decoded an unmodified source photograph
using `probe/decode-panic-qr.py`; temporary reader environment is
`/tmp/azahi-panic-qr.ePlvmP`. Neither decoder follows decoded URLs. Whole-frame
text OCR is unreliable at the tiny console font size; don't infer text from
its failed recognition.
