if [ "$(tty)" = /dev/tty1 ] && [ ! -e /run/native-rootguard-requested ]; then
    : > /run/native-rootguard-requested
    systemctl start --no-block native-rootguard-check.service
fi
