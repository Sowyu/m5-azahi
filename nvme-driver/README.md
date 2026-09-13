# ANS / SART storage experiments

The original native diagnostic blocks media writes. A separate private
rootguard variant allowed audited Linux-root writes and supported SSD KDE.
The source includes split NVMe/NVMMU mapping, explicit buffer registration,
SARTv4 handling and command-policy tests. Unmodified source references remain
in `vendor/` with their original notices.

Public disk identifiers are invalid placeholders. **Public rootguard kernel
builds are blocked**: the historical bounds must never be reused on another
disk. The host boundary test remains runnable and does not access hardware.

These software checks do not prove that experimental firmware/DMA behavior
cannot damage storage. Never touch the daily-driving macOS partition and do
not use reset or vendor commands as an attempted recovery shortcut.
