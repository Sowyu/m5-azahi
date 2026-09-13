# RAM diagnostic only: request the test once if normal target startup skipped it.
if [ "$(tty)" = /dev/tty1 ] && [ ! -e /run/native-ssd-ro-requested ]; then
    : > /run/native-ssd-ro-requested
    systemctl start --no-block native-ssd-ro-check.service
fi
