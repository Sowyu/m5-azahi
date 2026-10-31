#!/bin/bash
set -euo pipefail
release=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
patch=/sys/kernel/livepatch/azahi_input_recovery
if [[ ! -d "$patch" ]]; then
    insmod "$release/azahi_input_recovery.ko" afe_reset=1
fi
[[ $(cat "$patch/enabled") == 1 ]]
[[ $(cat /sys/module/azahi_input_recovery/parameters/afe_reset) == Y ]]
for ((attempt=0; attempt<100; attempt++)); do
    [[ $(cat "$patch/transition") == 0 ]] && break
    sleep 0.1
done
[[ $(cat "$patch/transition") == 0 ]]
# Opening the event device invokes the standard HID open path. Already-ready
# hardware is untouched; the patch permits just one reset/retry on failure.
event_path=$(python3 - <<'PY'
import os
from pathlib import Path
paths = [p for p in Path('/sys/class/input').glob('event*')
         if (p / 'device/name').read_text().strip() == 'Apple MTP multi-touch']
if len(paths) != 1:
    raise SystemExit('Expected one MTP trackpad event device')
path = paths[0]
fd = os.open('/dev/input/' + path.name, os.O_RDONLY | os.O_NONBLOCK)
os.close(fd)
print(path)
PY
)
udevadm trigger --action=add "$event_path"
printf '%s\n' 'Trackpad is ready; failed-start recovery is armed for this boot.'
