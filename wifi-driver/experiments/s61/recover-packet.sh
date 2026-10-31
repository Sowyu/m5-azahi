#!/usr/bin/env bash
# Host frontend rollback only. Never resets or unloads a DMA owner.
set -euo pipefail
exec 8>/run/azahi-n1-frontend.lock
flock -w 20 8
bundle=/opt/azahi-wifi/current
config=/etc/azahi-wifi
check() { [[ $(cat "/sys/module/$1/parameters/result") == 0 ]]; }
for m in n1_alpha_transport_v9 n1_alpha_data_rx_v2 n1_alpha_data_tx_v2; do check "$m"; done
if [[ -d /sys/module/n1_wifi ]]; then
    for dev in /sys/class/net/*; do
        [[ -d $dev/phy80211 ]] || continue
        nmcli --wait 10 device disconnect "${dev##*/}" || true
        ip link set "${dev##*/}" down
    done
    rmmod n1_wifi
fi
IFS= read -r mac < "$config/station-mac"
if [[ ! -d /sys/module/n1_packet_netdev ]]; then
    if ! insmod "$bundle/s55/n1-packet-netdev.ko" mac="$mac" llc_tx=1 2>/dev/null; then
        [[ ! -d /sys/module/n1_connect_v9 ]] || rmmod n1_connect_v9
        insmod "$bundle/s53/n1-connect-v9.ko"
        python3 - "$config/fallback-connect.bin" <<'PY'
import os, sys
with open(sys.argv[1], 'rb') as f: request=bytearray(f.read(74))
assert len(request)==73
try:
    fd=os.open('/proc/n1_connect_v9',os.O_WRONLY)
    try: assert os.write(fd,request)==len(request)
    finally: os.close(fd)
finally: request[:]=bytes(len(request))
PY
        check n1_connect_v9
        rmmod n1_connect_v9
        for ((i=0;i<100;i++)); do
            if insmod "$bundle/s55/n1-packet-netdev.ko" mac="$mac" llc_tx=1 2>/dev/null; then break; fi
            sleep 0.2
        done
    fi
fi
[[ -e /sys/class/net/n1data0 ]]
IFS= read -r profile < "$config/fallback-profile"
nmcli connection modify "$profile" connection.autoconnect yes
nmcli --wait 40 connection up "$profile" ifname n1data0 >/dev/null
printf '%s\n' 'N1_PACKET_RECOVERED'
