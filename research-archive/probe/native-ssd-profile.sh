if [ "$(tty)" = /dev/tty1 ]; then
    echo '=== SSD ROOT BOOT ==='
    findmnt -n -o SOURCE,FSTYPE,OPTIONS /
    printf 'CPU online: '; cat /sys/devices/system/cpu/online
    echo 'Starting KDE in 5 seconds; root filesystem is on SSD, kernel still USB-loaded.'
    sleep 5
    exec /bin/bash /usr/local/bin/native-ssd-kde-start
fi
