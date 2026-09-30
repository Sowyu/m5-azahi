# Native N1 experiment source checkpoint

These are handwritten Linux modules and protocol encoders, with their original
numbered dependencies preserved. No Apple firmware or disassembly is included.
Target: J714s/T6050, kernel `7.0.13-400.asahi.fc44.aarch64+16k`.

| Source | State at publication |
| --- | --- |
| s0, s1, s2 | N1 GP power/link, private PCIe host and runtime device tree |
| s3r, s4e, s5 | Signed ROM transfer, preboot cleanup and N1-only port cycle |
| s7survey, s19 | Runtime survey; control firmware and Alpha memswap handoff |
| s41–s43 | Fresh continuous command/event transport, bounded callers, passive cfg80211 scan |
| s44, s46 | Superseded data queues, retained for exact reset ABI/history; s44 rejects real kind-3 RX |
| s45, s53 | Root-only, one-attempt connection submission; PMK never logged |
| s47, s48 | Host-RAM snapshot; reset with unchanged working image (failed after association) |
| s54 | Successful reset after restoring the boot-populated memswap image |
| s49, s52 | Active transport after s54 and bounded query/station/scan caller |
| s50, s51 | Active RX and TX queues; real RX observed, TX not yet exercised |
| s55 | Temporary packet netdev; built, not loaded at this checkpoint |
| common | Bounded ACI encoders/decoders and TX metadata helpers |

`preboot-fresh-boot.sh` is an explicit runtime bring-up script for a fresh target
boot. Its target staging path is an experiment convention, not an installer.
It stops before starting the main control firmware. All numbered modules have
specific state assumptions. Do not automate replay of the historical sequence.

Build each module against the exact target kernel headers. Companion modules
require the corresponding transport `Module.symvers` via
`KBUILD_EXTRA_SYMBOLS`. S55 additionally needs S50 and S51 symbols; S48/S54
need S41, S44 and S46 symbols. Keep the directory layout for relative headers.
The top-level `wifi-driver/Kbuild` builds the earlier ROM experiments only.

The modules retain published DMA, including on errors. S54 resets only the
Alpha PCI function after reset-ready and no-pending-transaction checks; all old
DMA remains pinned. No shared host/storage reset or BAR4 crash-window read is
part of this checkpoint. There is no general remove/resume/recovery lifecycle.

Validated live: signed firmware boot, command/reply wraparound, station start,
passive scans, WPA2 association/offloaded handshake, RX descriptor wraparound,
and Alpha-only recovery without losing tethering. W=1 target builds passed for
S41–S55 used in this checkpoint. Missing optional BTF tooling was the only build
notice. Connection/metadata encoders were additionally compared privately with
isolated native instructions and the running firmware's TLV parser.

Remaining: TX packet delivery, IP configuration and end-to-end traffic, a proper
cfg80211 connection interface, bounded high-rate RX delivery, reconnect/reboot
lifecycle and power management. The temporary Ethernet frontend is a packet
validation tool and does not replace Linux wireless integration.
