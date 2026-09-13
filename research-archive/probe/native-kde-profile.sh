# Installed only in the disposable RAM root, not on the SSD or host image.
if [ "$(tty)" = /dev/tty1 ] && command -v kwin_wayland >/dev/null; then
    exec /bin/bash /usr/local/bin/native-kde-start
fi
