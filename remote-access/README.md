# Authenticated native access

This is a task-specific SSH relay for a native Linux laptop behind phone
tethering NAT. It does not enable the helper's operating-system SSH login,
expose a native root login on the LAN, or configure router/firewall forwarding.
Helper and phone must have a route between them; same Wi-Fi is not proof of
reachability until the connection succeeds.

`relay.py init` takes an empty private directory, the helper's IPv4 address
and the exact private Linux-root UUID. It generates three independent Ed25519
keys, a 64-bit one-use bootstrap password, and a target setup artifact.
All generated state is PRIVATE. Never copy it into the public repository.
Initialize outside this source directory with restrictive permissions.

The helper relay uses pinned `requirements.txt` in a dedicated environment.
`serve` listens on the selected helper address, port 8022. The virtual setup
account accepts only the bootstrap command, expires 20 minutes after the
first `serve` start, and is disabled after delivery. At most five failed
password attempts are allowed. The window, the failure count and delivery are
recorded in the private directory, so a relay restart resets none of them.
It has no host shell.

`init` and `serve` print the relay host-key SHA256 fingerprint
(`RELAY_HOST_KEY`). The user must compare it with the fingerprint the SSH
client shows before accepting it. The setup artifact and task-scoped tunnel
private key travel only over that authenticated encrypted SSH connection.
The controller private key stays on the helper. No passwords/private keys
belong in documentation, shell history, screenshots or publication. Never use
disabled host checking.

The Linux setup body refuses the wrong kernel, model or root UUID. It creates
only unique `/run` state and two transient systemd services. A dedicated native
OpenSSH daemon listens on loopback port 2222 with key-only root access and no
forwarding, agent, X11 or user-RC support. Existing sshd config and authorized
keys are untouched. The native host key is generated locally and registered
over the authenticated relay; replacements are refused. The tunnel's key can
request only the helper's loopback port 22022 after registration. It cannot
run commands on the helper or create arbitrary forwards. The helper then
uses the controller key and registered native host pin to connect through it.

The source is an initial prototype, not a general-purpose audited access
product. Six real loopback tests cover incorrect credentials,
host-key mismatch, one-use bootstrap, command/local-forwarding refusal,
registration pinning, loopback-only remote forwarding, actual data through
that forward, expiry/lockout surviving a restart and fingerprint output.
Run `python test-relay.py` inside the dedicated environment.
No target is accessed by these tests. The tests use an isolated ephemeral
forwarding port, so they can run while the production relay is occupied.
Native key-authenticated access and a live switch to the persisted services
have now been verified, followed by certificate-validated HTTPS GET success.

Bootstrap services are temporary and do not survive a reboot. The setup prints their
exact names and a stop command. Stopping the two task services revokes the
native session; stopping the helper relay closes its listener and forwards.
Do not delete unrelated keys, configurations, user directories or services.
No partitions, bootloader, USB driver or macOS volume are modified here.

## Optional persistent services

`persist.py` accepts the verified bootstrap runtime directory, expected private
Linux root UUID and helper IPv4 as arguments. It refuses preexisting dedicated
state/units, checks the model/kernel/root and refuses any APFS mount. It copies
only task-specific state to `/var/lib/azahi-remote`, validates the isolated
sshd config, and enables `azahi-native-sshd` and `azahi-native-tunnel`.
It adds the dedicated `azahi-usb-tether` NetworkManager autoconnect profile,
without replacing the currently active connection. The installer does not
start conflicting listeners; an attended, rollback-protected live transition
is a separate step. These services are installed and live-tested on the
research machine. One subsequent cold boot also verified automatic tunnel
reconnection, the saved USB profile and certificate-validated HTTPS. That
boot required empty USB-C sockets until KDE loaded, then phone connection
and tethering enabled on the phone. This is not a general reliability claim.

The tunnel needs this helper relay running and reachable at its configured
address; it is not independent cloud access. The laptop's internet connection
does not require the helper once native USB initialization works at boot.
Stopping the persistent tunnel/sshd units and disabling them revokes this
access path. Keep private state and absence/installation receipts private.
