# Native N1 experiment source checkpoint

These are handwritten Linux modules and protocol encoders, with their original
numbered dependencies preserved. No Apple firmware or disassembly is included.
Target: J714s/T6050, kernel `7.0.13-400.asahi.fc44.aarch64+16k`.

October 31 validation now demonstrates DHCP, DNS, ICMP and HTTPS over native
N1 using S55's opt-in `llc_tx=1` payload conversion. A bulk HTTPS download
matched an independent copy by SHA-256. The firmware-generated 802.11
destination still addresses the AP; general LAN bridging and IPv6 remain
unvalidated. This is a working experimental gateway path with unchanged DMA
ownership. A guarded startup bundle now passes a fresh reboot on the pinned
target, but the public sources are not a general installer.

S61 registers a cfg80211 station with passive 2.4/5 GHz scanning. DHCP/HTTPS,
reconnect, radio off/on, roaming and direct RX under a 2.49 MB download test are
verified. A missing BSSID in the connection-success notification caused a kernel
fault; the corrected notification and regression test are included. Installed
boot selection is now S61. A warm restart reached an Apple boot alert; cold boot
recovered Fedora but exposed a NetworkManager readiness race and used S55.
The startup script now waits for the matching Wi-Fi device to become ready;
its cold-boot verification is pending. See the handoff.

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
| s50, s51 | RX and TX carry native IPv4 with S55 LLC/SNAP conversion |
| s55 | Opt-in `llc_tx=1`: native DHCP, DNS, ICMP and HTTPS verified |
| s56 | Separate MCBC queue accepted live; two broadcast probes completed but got no reply |
| s57 | Exact station-counter query validated live; link headers can remain stale after disconnect |
| s61 | Normal Wi-Fi scans, DHCP/HTTPS, reconnect, roaming and host-only recovery verified; boot verification pending |
| s62 | Host-only disconnect helper for the fresh single-TX-ring bundle; caller must remove all packet frontends |
| common | Bounded ACI encoders/decoders and TX metadata helpers |

The S61 directory also contains the model/kernel-pinned startup service and
host-frontend recovery script. They depend on a separately prepared root-only
configuration, signed firmware and a checked module bundle, none included here.
They never force-unload DMA owners. A successful build is not authorization to
load a probe into an unknown ownership state.

S49's link cache separates connection lifetime from the rolling diagnostic
history. S50 offers a single direct RX consumer with synchronized detach, and
S51 exposes outstanding TX count. Synthetic checks are available in
`test_link_state.c`, `test_rx_consumer.py`, `test_wifi_security.py` and
`test_wifi_notification.py` in the parent directory. `test_wifi_startup.py`
exercises the actual shell readiness gate with a mocked NetworkManager.
These tests complement the live
checks and do not establish long-duration stability. The generalized 20 MHz
channel encoder covers 13 2.4 GHz and 25 5 GHz
candidates, subject to cfg80211 regulatory limits.

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

Remaining: general LAN destination handling, IPv6 validation, automatic
cfg80211 boot verification, extended load/stability checks and power management.
The temporary Ethernet frontend remains a packet validation/recovery tool;
S61 supplies the wireless integration for open/WPA2-PSK CCMP networks.

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

### Experimental raw MSDU conversion

`llc_tx=1` is read-only after module load and defaults to off. The helper strips
the Ethernet addresses, inserts RFC1042 LLC/SNAP, and preserves EtherType and
network payload. Length-coded 802.3 and bridge-tunnel exceptions are rejected.
It cannot change the firmware-generated destination; do not describe this as
complete Ethernet encapsulation support. Firmware still handles encryption.

```sh
cc -std=c11 -Wall -Wextra -Werror -fsanitize=address,undefined \
  -I wifi-driver/experiments/common wifi-driver/test_tx_msdu.c \
  -o /tmp/n1-tx-msdu-test
/tmp/n1-tx-msdu-test
```

S55 still requires a retained successful connection event at initialization.
After it ages out, a controlled disconnect/reconnect must supply fresh evidence
before loading the frontend. Boot automation must not bypass that check.
