#!/bin/bash
set -euo pipefail
release=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
module=/sys/module/azahi_power/parameters
if [[ ! -d "$module" ]]; then
    modprobe macsmc
    insmod "$release/azahi_power.ko" enable=1
fi
[[ $(cat "$module/enable") == Y ]]
[[ $(cat "$module/result") == 0 ]]
[[ $(cat "$module/ready") == Y ]]
printf '%s\n' 'J714s shutdown and restart handlers are ready.'
