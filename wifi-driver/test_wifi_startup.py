#!/usr/bin/env python3
"""Test the real startup readiness gate without NetworkManager or hardware."""
import os
from pathlib import Path
import re
import subprocess
import tempfile

root=Path(os.environ.get('N1_SOURCE_ROOT',Path(__file__).with_name('experiments')))
source=(root/'s61/start-native-wifi.sh').read_text()
match=re.search(r'^wait_wifi_ready\(\) \{.*?^\}',source,re.M|re.S)
assert match
script=r'''
set -euo pipefail
sleep_count=0
sleep() { sleep_count=$((sleep_count+1)); }
nmcli() {
    [[ $* == '-g GENERAL.STATE device show wlan-test' ]] || exit 99
    local count
    read -r count < "$N1_TEST_COUNTER"
    printf '%s\n' "$((count+1))" > "$N1_TEST_COUNTER"
    case $scenario in
        ready) printf '%s\n' '100 (connected)' ;;
        delayed)
            case $count in
                0) return 10 ;;
                1) printf '%s\n' '10 (unmanaged)' ;;
                2) printf '%s\n' '20 (unavailable)' ;;
                *) printf '%s\n' '30 (disconnected)' ;;
            esac ;;
        unavailable) printf '%s\n' '20 (unavailable)' ;;
        failed) printf '%s\n' '120 (failed)' ;;
    esac
}
''' + match.group() + r'''
for scenario in ready delayed unavailable failed; do
    printf '0\n' > "$N1_TEST_COUNTER"
    sleep_count=0
    if wait_wifi_ready wlan-test; then result=0; else result=$?; fi
    read -r queries < "$N1_TEST_COUNTER"
    case $scenario in
        ready) [[ $result == 0 && $queries == 1 && $sleep_count == 0 ]] ;;
        delayed) [[ $result == 0 && $queries == 4 && $sleep_count == 3 ]] ;;
        *) [[ $result == 1 && $queries == 100 && $sleep_count == 100 ]] ;;
    esac
done
printf '%s\n' 'PASS: delayed supplicant readiness, already connected, and bounded unavailable/failed timeout'
'''
with tempfile.TemporaryDirectory(prefix='n1-startup-test-') as directory:
    env=dict(os.environ,N1_TEST_COUNTER=str(Path(directory)/'counter'))
    subprocess.run(['bash','-c',script],env=env,check=True)
