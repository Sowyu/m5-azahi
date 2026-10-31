#!/bin/bash
# Wraps the pinned /opt/azahi-usb/start-native-usb.sh. Only a clean HPM
# refusal (azahi_hpm_once result -11, not poisoned: unsupported system state)
# becomes exit 75, which azahi-usb.service retries with a
# bounded start limit. Every other outcome is passed through unchanged, so
# poisoned or other failures never loop. Added 2026-09-29.
params=${AZAHI_HPM_PARAMS:-/sys/module/azahi_hpm_once/parameters}
"${AZAHI_USB_START:-/opt/azahi-usb/start-native-usb.sh}"
rc=$?
if [[ $rc -ne 0 && -d $params && $(< "$params/result") = -11 && $(< "$params/poisoned") = N ]]; then
    echo 'USB_WAITING: controller system state not ready; bounded startup retry scheduled'
    exit 75
fi
exit $rc
