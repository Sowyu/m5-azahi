# Native N1 experiment source checkpoint

These are handwritten Linux modules and protocol encoders, with their original
numbered dependencies preserved. No Apple firmware or disassembly is included.
Target: J714s/T6050, kernel `7.0.13-400.asahi.fc44.aarch64+16k`.

October 31 fresh-boot validation reproduced signed firmware startup, native
scan, WPA2 association and packet reception. S49–S55 built on the target and
S55 registered successfully. The first TX exposed an unsupported batch format;
the corrected S51 decoder is built, sanitizer-tested and verified to accept
repeated live completions with firmware success. ARP and DHCP got no replies,
so packet delivery and native IP connectivity remain unproven.
The table distinguishes the current path from historical recovery experiments.

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
| s49, s52 | Fresh S19 transport verified live; bounded query/station/all-channel passive scan caller |
| s50, s51 | RX verified; corrected TX decoder accepts live completions, packet delivery still unproven |
| s55 | Temporary packet netdev registered live; no native IP result yet |
| s56 | Separate MCBC queue accepted live; two broadcast probes completed but got no reply |
| s57 | Exact station-counter query caller; revised S49 support built/tested, fresh-boot validation pending |
| common | Bounded ACI encoders/decoders and TX metadata helpers |

`preboot-fresh-boot.sh` is an explicit runtime bring-up script for a fresh target
boot. Its target staging path is an experiment convention, not an installer.
It stops before starting the main control firmware. All numbered modules have
specific state assumptions. Do not automate replay of the historical sequence.

S49 defaults to requiring the exact S54 reset marker. `fresh=1` selects the
fresh S19 handoff and rejects any previous Alpha owner; it performs no reset
or cleanup. Both modes retain the firmware, PCI and IOMMU preflight. `launch`
still defaults to false. Select a mode only after verifying the current boot
and ownership, not to make an unexpected state pass.

Run `python3 wifi-driver/test_lifecycle.py` from the repository root to test
the actual S49 owner predicate, exact station-counter request gate and S55 stop callback with synthetic state.
The tests do not exercise hardware or substitute for a target build and live
validation of DMA, packet delivery and shutdown behavior.

Test the portable TX completion decoder with synthetic data, including every
legal batch placement and missing-member rejection:

```sh
cc -std=c11 -Wall -Wextra -Werror -fsanitize=address,undefined \
  -I wifi-driver/experiments/common wifi-driver/test_tx_completion.c \
  -o /tmp/n1-tx-completion-test
/tmp/n1-tx-completion-test
```

Build each module against the exact target kernel headers. Companion modules
require the corresponding transport `Module.symvers` via
`KBUILD_EXTRA_SYMBOLS`. S55 additionally needs S50 and S51 symbols; S56 needs S49 and S51, and S57 needs S49; S48/S54
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

The MCBC probe uses separate data-ring slots and the native broadcast peer,
AC3/TID6 client data. It retains every published allocation. Its root-only proc
write accepts one bounded multicast Ethernet frame; it is not connected to the
packet netdev. S56 has an exact checkpoint guard, not a reusable loader.
The default station queue's zero peer address was also confirmed in the native
setup, so neither peer form has been identified as the missing IP-path fix.

S57 requests only global station-counter source 37 with one scope TLV. The
previous loaded S49 refused it before submission; the revised S49 admits only
the exact 46-byte request, with ACK-only completion disabled. Host tests reject
truncation, extra data and every single-bit change to its payload. A fresh boot
is required to use the rebuilt DMA-owning S49; do not patch or force-unload it.
