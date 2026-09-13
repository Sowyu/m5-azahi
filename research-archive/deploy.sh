#!/bin/sh
# Push the current bring-up artifacts to the M1 Pro host and verify them.
# Run when the host Mac is connected:  sh deploy.sh
set -e
H=PRIVATE-USER@PRIVATE-LAN-ENDPOINT-REMOVED
K=~/.ssh/id_ed25519_azahi
D="$(cd "$(dirname "$0")" && pwd)"

ssh -i $K -o BatchMode=yes -o ConnectTimeout=5 $H 'echo host up' >/dev/null 2>&1 || {
    echo "M1 Pro not reachable at $H - connect it and retry."; exit 1; }

scp -i $K "$D/m1n1-vmtmrfix.bin" \
          "$D/guest-hv.bin" \
          "$D/proxy-kit/vmtmrprobe.py" \
          "$D/proxy-kit/hv-fixed.sh" \
          "$D/proxy-kit/hv.sh" \
          $H:'~/azahi/'

# host-side hypervisor (PMGR shadow fix + T6050 CPUSTART entry)
scp -i $K "$D/m1n1/proxyclient/m1n1/hv/__init__.py" $H:'~/azahi/proxyclient/m1n1/hv/__init__.py'

echo "--- verifying ---"
ssh -i $K -o BatchMode=yes $H 'cd ~/azahi && shasum -a256 m1n1-vmtmrfix.bin guest-hv.bin vmtmrprobe.py hv-fixed.sh hv.sh && python3 -m py_compile vmtmrprobe.py && sh -n hv-fixed.sh && sh -n hv.sh && echo "ALL OK"'
echo "--- local, for comparison ---"
shasum -a256 "$D/m1n1-vmtmrfix.bin" "$D/guest-hv.bin" "$D/proxy-kit/vmtmrprobe.py" "$D/proxy-kit/hv-fixed.sh" "$D/proxy-kit/hv.sh" | sed 's|  .*/|  |'
