# Phone SSH and laptop web access through a USB cable

This is an untested fallback for the J714s while phone tethering is broken.
ADB can carry a TCP connection over USB without creating a Linux network
interface. The laptop remains the USB host. The helper below asks ADB to make
the phone's loopback port reach the laptop's loopback SSH service.
The [ADB manual](https://android.googlesource.com/platform/packages/modules/adb/+/refs/heads/main/docs/user/adb.1.md)
documents reverse forwarding and the USB-only `-d` selector.

This does not repair USB enumeration or reconnect the home server. SSH alone
does not provide internet. The optional proxy section below can carry web
traffic through the phone's connection. Both endpoints need their programs.
The Fedora package is
[`android-tools`](https://packages.fedoraproject.org/pkgs/android-tools/android-tools/fedora-44.html).
Use its AArch64 build on this laptop. Termux provides an
[`openssh` package](https://github.com/termux/termux-packages/tree/master/packages/openssh)
for the phone. Package installation needs downloads or prepared offline
packages; the cable does not solve that initial dependency.

## Prepared offline laptop bundle

A local candidate, `portable-adb-37.0.0-j714s-v2.tar.gz`, contains Fedora's
AArch64 ADB 37.0.0-4.fc44, twelve private libraries, their license files and
the protocol helper, proxy configuration and this setup guide.
It is 5,271,533 bytes, with SHA-256
`22ea6512f002a99cd013f28e759d5bade3871d1dd7b634de62a607fb284c96b9`.
It remains on the home server, unpublished and uninstalled.

After transferring and extracting it into a new laptop directory, run
`./adb version` there. Use `./adb` instead of `adb` in the instructions below.
Run `python3 phone-cable.py` from its directory instead of the repository
path below. Version 2 includes the optional `--internet` mode; the preserved
first bundle supports SSH only. The launcher checks the board, kernel and
file hashes. It sets its
library path for ADB only and changes no system files. It does not install
USB permission rules or phone software.

The signed RPMs were verified against
[Fedora's published signing key](https://fedoraproject.org/security/).
ADB and the private libraries use the laptop's existing glibc and loader;
they require symbol versions through `GLIBC_2.39`. No glibc or kernel
replacement is included. Missing symbols are a failed preflight, not a
reason to replace system libraries. All shipped ELF load segments align to
64 KiB, covering the target's 16 KiB pages. ADB runs under ARM emulation,
including an emulated 16 KiB page setting; physical USB remains untested.

## Prepare phone authentication once

The existing task SSH service listens on laptop loopback port 2222. It only
accepts keys listed in `/var/lib/azahi-remote/controller.pub`. The home
controller's private key stays on the home server. Create a separate phone
key instead.

1. In Termux, run `pkg install openssh` if needed, then
   `ssh-keygen -t ed25519 -f ~/.ssh/m5_phone`. Choose a passphrase. If that
   filename already exists, preserve it rather than overwriting it.
2. Run `cat ~/.ssh/m5_phone.pub` on the phone. Copy only that public
   `ssh-ed25519` line to a text file named `m5-phone.pub` on the laptop.
   The file without `.pub` is private and stays on the phone.
3. In the laptop's Konsole, check the public key with
   `ssh-keygen -lf m5-phone.pub`. It must match the fingerprint printed by
   `ssh-keygen -lf ~/.ssh/m5_phone.pub` on the phone.
4. On the laptop, make a separate backup before adding the public key:

   ```sh
   sudo sh -eu -c '
     phone_key_backup=$(mktemp /var/lib/azahi-remote/controller.pub.before-phone.XXXXXX)
     cp -p /var/lib/azahi-remote/controller.pub "$phone_key_backup"
     cat >> /var/lib/azahi-remote/controller.pub
   ' < m5-phone.pub
   ```

   Stop if a command fails. This grants the phone the existing task's root
   shell access. The daemon reads the key file for new connections; no
   service restart or main SSH configuration change is needed.
5. On the laptop, record its host-key fingerprint with
   `sudo ssh-keygen -lf /var/lib/azahi-remote/host_key.pub`. Compare this
   exact fingerprint at the phone's first SSH connection below.

## Connect

1. Boot with USB-C sockets empty. Wait for KDE, start the existing
   `azahi-usb` service, and check its journal for `USB_HOST_READY` or
   `USB_ALREADY_READY`. Keep the current drivers loaded.
2. Enable USB debugging on the phone, connect it to the right-hand socket,
   and run `adb -d get-state` in the laptop's Konsole. Unlock the phone and
   approve this laptop's debugging prompt. The command must report `device`.
   Android requires this [on-device authorization](https://developer.android.com/tools/adb#Enabling).
3. Check `systemctl is-active azahi-native-sshd` on the laptop. It must
   report `active`. From this repository's directory, run:

   ```sh
   python3 remote-access/phone-cable.py
   adb -d reverse --list
   ```

   The listing must show phone port 2222 forwarding to `tcp:localhost:2222`.
   ADB may normalize the phone endpoint to `tcp:2222` in that listing.
   The helper sends explicit loopback addresses. Android's
   [socket implementation](https://android.googlesource.com/platform/packages/modules/adb/+/refs/heads/main/socket_spec.cpp)
   binds a bare `tcp:2222` listener to all interfaces. The stock CLI rejects
   host-qualified TCP endpoints, so the helper sends ADB's framed protocol
   to the existing server on `127.0.0.1:5037`. It selects USB only, checks
   the existing SSH banner, and uses `norebind` to preserve an existing
   mapping. Both tunnel endpoints are fixed to `tcp:localhost:2222`.
   A refusal has no fallback to a broader listener. Inspect the listing
   before retrying after an error, since a lost reply can follow a
   successful listener creation.
4. In Termux on the phone, run:

   ```sh
   ssh -p 2222 -i ~/.ssh/m5_phone -o IdentitiesOnly=yes -o HostKeyAlias=azahi-m5-phone root@127.0.0.1
   ```

   Compare the host fingerprint from preparation before accepting it.
   A root prompt on the laptop and `uname -r` showing the pinned kernel
   establish an actual shell connection. A successful `adb reverse` alone
   does not test SSH authentication or USB stability.
5. Keep the cable connected while debugging. After unplugging or rebooting,
   inspect and recreate the mapping as needed. To close this mapping while
   connected, run `adb -d reverse --remove tcp:2222` on the laptop. To revoke
   the phone's future SSH access, remove only its public-key line from the
   task key file, keeping the backup and home controller's key.

If ADB reports `unauthorized`, authorize it on the phone. `offline`, a missing
device, or USB `-71` errors mean this route is not ready. Do not unload the
live USB stack or restart its controller as a recovery attempt. This path
needs a real phone-to-laptop test before it can be called working.

## Optional web access through the phone

The phone needs a working cellular or Wi-Fi connection and Termux's
[`tinyproxy` package](https://github.com/termux/termux-packages/blob/master/packages/tinyproxy/build.sh).
This carries HTTP and HTTPS for configured programs. It does not create a
network interface, carry UDP or give every application internet access.
Both proxy endpoints stay on loopback. No root access is needed on Android.

1. In Termux, run `pkg install tinyproxy`. Create a separate configuration
   without replacing an existing file:

   ```sh
   phone_proxy_config=$(mktemp "$HOME/m5-phone-proxy.XXXXXX.conf")
   cat > "$phone_proxy_config" <<'EOF'
   Port 8118
   Listen 127.0.0.1
   Allow 127.0.0.1
   ConnectPort 443
   Timeout 300
   MaxClients 16
   LogLevel Warning
   ViaProxyName "m5-phone"
   EOF
   tinyproxy -d -c "$phone_proxy_config"
   ```

   Keep this Termux session running. These are the directives in
   [phone-proxy.conf](phone-proxy.conf). The
   [Tinyproxy manual](https://tinyproxy.github.io/) describes foreground
   operation and HTTPS CONNECT. The proxy passes TLS through; it does not
   install certificates or decrypt HTTPS.
2. After the earlier USB authorization step reports `device`, run on the
   laptop from the current repository:

   ```sh
   python3 remote-access/phone-cable.py --internet
   adb -d forward --list
   ```

   The listing must map laptop `tcp:8118` to phone `tcp:localhost:8118`.
   The helper requests an explicit localhost listener with `norebind` and
   USB-only selection. An existing listener is preserved. This mode does
   not require the separate SSH service or phone SSH key.
3. Test verified HTTPS from the laptop:

   ```sh
   curl --proxy http://127.0.0.1:8118 --noproxy '' --head --fail --show-error --max-time 30 https://fedoraproject.org/
   ```

   A successful HTTP response establishes this request through the proxy.
   Tunnel creation alone proves neither phone connectivity nor HTTPS.
   Certificate errors require checking the laptop's clock and certificate
   store. The clock procedure below works over the earlier SSH connection.
   Never bypass certificate verification.
4. For Firefox, record its existing proxy setting, open Settings and search
   for `proxy`. Choose manual configuration with HTTP proxy `127.0.0.1`,
   port `8118`, and enable the option to use it for HTTPS. Leave SOCKS blank.
   [Mozilla documents these controls](https://support.mozilla.org/en-US/kb/connection-settings-firefox).
   Only CONNECT port 443 is allowed by this config. A command can use the
   proxy without changing global settings, for example:

   ```sh
   git -c http.proxy=http://127.0.0.1:8118 ls-remote https://github.com/Sowyu/m5-azahi.git HEAD
   ```

   The reviewed source fixes are on `audit-2026-09-25` in
   [PR #5](https://github.com/Sowyu/m5-azahi/pull/5). To download a separate
   checkout through the proxy:

   ```sh
   git -c http.proxy=http://127.0.0.1:8118 clone --single-branch --branch audit-2026-09-25 https://github.com/Sowyu/m5-azahi.git m5-azahi-audit
   ```

   Choose a new destination directory. This downloads source; it does not
   install modules or a boot image. Build artifacts remain on the home server.
5. To stop, restore Firefox's previous proxy setting, close this forward with
   `adb -d forward --remove tcp:8118`, and press Ctrl+C in the phone's proxy
   session. This closes network listeners and preserves the config file.
   If Android stops Termux or the USB connection drops, the proxy stops
   working. Inspect both ends before recreating the mapping.

## If the laptop's date is wrong

This HTTP proxy does not carry NTP's UDP traffic. Restarting chronyd cannot
obtain time through this proxy alone. Chrony's
[server port documentation](https://chrony-project.org/doc/4.8/chrony.conf.html)
specifies UDP, normally port 123. The earlier native tethering connection
could carry NTP; the proxy has a narrower scope.

With the phone-to-laptop SSH connection already working, use the phone's
clock for an initial correction. This takes about one minute.

1. Check that Android's automatic date and time is enabled and its displayed
   date is correct. In Termux, run `date -u` and check the UTC date too.
2. Run this in Termux. It sets the **laptop's** system clock using the phone's
   current Unix timestamp and prints the resulting UTC time:

   ```sh
   phone_epoch=$(date +%s)
   ssh -p 2222 -i ~/.ssh/m5_phone -o IdentitiesOnly=yes -o HostKeyAlias=azahi-m5-phone root@127.0.0.1 "date -u --set=@$phone_epoch"
   ```

Use the already-verified laptop host key. SSH authentication delays make this
an approximate initial correction, not precise synchronization. Retry the
certificate-verified HTTPS command above afterwards. This does not configure
NTP, write the hardware clock or prove that the date survives another boot.
The laptop's NTP synchronization flag may remain false.

## Offline checks

`python3 remote-access/test-phone-cable.py` exercises the actual framed
requests against a fake ADB server on laptop loopback. It covers split and
truncated replies, both required acknowledgements, refused USB selection,
listener failures and refusal to run on the wrong machine. The protocol and
CLI limitation were checked against the Fedora 44 `android-tools`
35.0.2-17 and signed 37.0.0-4 source packages. The latter's host forwarding
allowlist tracks this exact destination. ARM emulation of its actual CLI
also reproduces the rejection of `tcp:localhost:2222`. No actual Android
daemon, cable or SSH authentication was tested. These checks do not establish
that the phone supports the path.

The expanded helper passes thirteen host groups, including USB-only proxy
selection, both required forward acknowledgements, listener refusals and
the target guard before any connection. A separate local integration check
with Debian Tinyproxy 1.11.2 passes HTTP, verified HTTPS, untrusted-certificate
and wrong-hostname refusals, blocked CONNECT ports, and loopback binding.
Only the test listener and origin ports change to ephemeral ports. The
Termux package currently builds 1.11.3; that Android binary, browser traffic
and the actual ADB data path remain untested.
