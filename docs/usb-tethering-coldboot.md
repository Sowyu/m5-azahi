# Cold-boot USB tethering failure

First cold boot of the installed v6 loader reached KDE, but the phone on the
right USB-C port did not charge and no tethering interface appeared. The
previous boot, where tethering worked, was a v6 RAM handoff from an attended
m1n1 proxy session. This note ranks the causes, gives the evidence, and lists
the commands that separate them. Nothing here is confirmed on hardware: the
service journal from the failed boot has not been read yet.

## The symptom already narrows the search

Only the USB-PD controller (HPM, reached over SPMI) sources VBUS on this port.
On the working boot it took one attended SSPS task to move the HPM from
state 7 to state 0, and only then was charging reported
(`usb-driver/pd-backport/README.md`, "Attended proxy diagnostic route").
No Linux driver in this tree turns VBUS on.

So "the phone does not charge" places the failure at or before the HPM step,
`usb-driver/start-native-usb.sh:39-52`. Everything after that line (the PHY,
overlay and DWC3 insmods) can only explain a missing interface, never a
missing charge. That demotes the whole driver-side story below the HPM story,
however plausible it looks on its own.

A second deduction comes from the guard itself. `hpm_awake_once` returns 0
immediately when the HPM is already in state 0
(`usb-driver/pd-backport/hpm-awake.h:98`), which would have set `ready=Y` and
let the script continue. It did not. So the HPM did not survive the power
cycle in S0: the cold boot really did put it back into some other state.

## Why the journal cannot answer this yet

The script ran under `set -euo pipefail` with several guards that produced no
output at all. A failed identity check, a failed `insmod`, and a failed
`modprobe` all ended the unit the same way, and `azahi_hpm_once` deregisters
itself whenever its init returns an error, so `/sys/module/azahi_hpm_once`
does not exist afterwards to be inspected. The single most useful change was
therefore to make every exit path name its step and print the HPM tuple. That
is what this branch does; the hardware-touching guards are untouched.

## Ranked causes

### 1. The HPM step failed. High confidence in the step, low in the sub-case

The HPM `insmod` either failed outright or the awake task refused. Both end
the script before any USB module loads, and both leave VBUS off.

Hard-failure paths, each of which makes `insmod` itself fail and abort the
script at `usb-driver/start-native-usb.sh:45`:

| `hpm-once.c` | Returns | `insmod` says | Meaning on a cold boot |
| --- | --- | --- | --- |
| :50 | `-ENODEV` | No such device | DT is not `apple,j714s` |
| :57 | `-EHOSTDOWN` | Host is down | SPMI controller power register not fully on |
| :59 | `-EBUSY` | Device or resource busy | Another driver claimed the SPMI region |
| :64 | `-EBUSY` | Device or resource busy | SPMI FIFO not idle at boot |
| :61 | `-ENOMEM` | Cannot allocate memory | `ioremap_np` failed |

Refusal paths, which load the module and leave a readable tuple:

| `hpm-awake.h` | `result` | Meaning |
| --- | --- | --- |
| :97 | -19 (ENODEV) | HPM not in application mode, or unexpected VID |
| :99, :100, :107 | -11 (EAGAIN) | Clean refusal: state or status is not the pinned disconnected tuple |
| :104 | -16 (EBUSY) | A task was already occupying the command slot |
| :63, :123 | -110 (ETIMEDOUT) | Selector or task polling gave up; **latches `poisoned=Y`** |
| :120, :126, :131 | -5 (EIO) | Unexpected task echo, nonzero result or bad readback; **latches `poisoned=Y`** |

The clean refusal at `hpm-awake.h:100` is the one the documented procedure
warns about: the tuple was pinned to an observation made from the proxy with
nothing plugged into the right port. If a partner was connected at boot, or if
the controller comes back from a real power cycle in a state that is neither 0
nor that exact tuple, the answer is -11 and nothing else happens. That is a
correct refusal, not a bug.

Against a simple -11: the user was told to boot with the phone unplugged
(`docs/HANDOFF.md`, "Earlier: corrected v6 installed"), and there is no
evidence yet either way about the charger cable. Also worth noting that a
`-110` or `-5` latch is permanent until reboot, because
`start-native-usb.sh:39` only re-checks after a clean refusal and
`hpm-once.c:77` pins the module when poisoned. A restarted service would then
report `HPM_NOT_READY` forever without touching the bus, which is the intended
behaviour.

### 2. Power-domain state the cold boot never inherits. Medium confidence, second blocker

This cannot explain the missing charge, so it is not the first failure. It is
still likely to bite as soon as the HPM question is settled.

The overlay refuses to apply unless five PMGR domains, including ATC2_USB, are
already active, and it says so explicitly: "loader-prepared power confirmed"
(`usb-driver/azahi-usb-overlay.c:83-89, 226-241`). There is no fallback. The
`pmgr` variant that would describe the domains is deliberately withheld
(`usb-driver/azahi-usb-overlay.c:234-237`). The PHY driver makes the same
assumption in prose: "The loader (m1n1 `usb_phy_bringup`) leaves the PHY
running in its device-mode configuration"
(`usb-driver/phy-apple-t6050-usb2.c:219-223`), and the DWC3 glue expects the
loader to have left the core out of reset through the pipehandler
(`usb-driver/dwc3-apple-t6050.c:8-9, 479`).

The two boots differ in exactly how much of that the loader did. The proxy
boot ran `usb_init()` **and** `usb_iodev_init()`
(`research-archive/standalone-loader/m1n1-20260911/src/main.c:89-90, 141-143`),
which is the path that brings the DWC3 side up for the proxy console. The cold
boot finds a valid payload, so it never takes that path; it reaches
`kboot_boot`, which calls only `usb_init()`
(`research-archive/standalone-loader/m1n1-20260911/src/kboot.c:2964`, reached
from `standalone-loader/m1n1-20260911/src/azahi_standalone.c:148`). The custom
loader component itself prepares ANS and one DART and nothing USB-related
(`azahi_standalone.c:43-86, 145`).

`src/usb.c` is not in this snapshot, so which of the five domains `usb_init()`
alone leaves active is not decidable from the repository. The overlay prints
all five with target and actual values at
`usb-driver/azahi-usb-overlay.c:102-104`, so one dry run answers it.

### 3. Identity or checksum guard. Low confidence

`start-native-usb.sh:18-23` checks kernel release, root UUID, DT compatible and
the module hashes. Both boots use the same v6 bundle, the same kernel and the
same root, so a mismatch would be surprising. It is cheap to rule out now that
each of these prints `STEP_FAILED`.

### 4. Missing network-class module aborting the script. Very low confidence

Under `set -e` a single failed `modprobe` used to abort everything before any
`insmod`. The pinned kernel config has all seven modules
(`research-archive/kconfig.txt:4019-4036, 9191, 9292, 10793`), so this is not
what happened, but it was one package change away from happening. The list is
now split into required and optional; a missing `cdc_ether` or `rndis_host`
logs `OPTIONAL_MODULE_MISSING` and continues.

### 5. Service timeout or ordering. Lowest confidence

`TimeoutStartSec=45` (`usb-driver/azahi-usb.service:11`) covers a 10-second hub
wait plus a few insmods, comfortably even on one core. `After=` ordering is
advisory only and nothing in the script needs NetworkManager. If the unit did
time out, `systemctl status` reports it as such and this note is wrong.

## Commands, in order

Read-only, safe with the current session preserved. Run them before touching
anything.

```sh
systemctl status azahi-usb
journalctl -u azahi-usb -b --no-pager
cat /sys/module/azahi_hpm_once/parameters/{result,ready,poisoned}
dmesg | grep -iE 'hpm|spmi|dwc3|xhci|phy|dart|usb'
ls /sys/bus/usb/devices
```

Reading the results:

- `status` says `inactive (dead)` and the journal is empty. The unit never
  ran. Check that it is enabled and that its condition path exists.
- `status` says `activating` or `timeout`. Cause 5; nothing else below applies.
- The journal ends at `STEP_FAILED: line 18` or `line 23`. Cause 3: identity or
  hash. The named line says which.
- The journal shows `insmod: ERROR: could not insert module ./azahi_hpm_once.ko`
  plus an errno phrase, and `HPM_TUPLE: azahi_hpm_once not loaded`. Cause 1,
  hard-failure half; use the errno table above.
- The journal shows `HPM_TUPLE: result=-11 ready=N poisoned=N` and
  `HPM_NOT_READY`. Clean refusal. Unplug everything from the right port, then
  `systemctl restart azahi-usb`. This is the only case a restart can fix.
- Any `HPM_TUPLE` with `poisoned=Y`. The bus is in an ambiguous state and stays
  latched until reboot. Do not restart the service, do not `rmmod`, do not
  retry the HPM. Collect `dmesg | grep azahi-hpm-once` and stop.
- `HPM_TUPLE: result=0 ready=Y poisoned=N` followed by an `insmod` failure on
  `azahi-usb-overlay.ko`. Cause 2. The preceding `azahi-usb-overlay: PMGR ...`
  lines name the domain that is not ACTIVE. In that case the phone should have
  been charging, which would contradict the reported symptom, so re-check the
  charge observation.
- `USB_HOST_READY` present but no `enu*` interface. Neither cause here; the
  problem is enumeration or NetworkManager, not startup.
- `ls /sys/bus/usb/devices` empty means no root hub of any kind: consistent
  with the script never reaching its insmods.

If the tuple and the journal clear the HPM but no root hub appears, one extra
read-only step settles cause 2. The dry run maps only always-on PMGR registers,
applies no overlay and creates no devices (`azahi-usb-overlay.c:229-232`):

```sh
insmod /opt/azahi-usb/azahi-usb-overlay.ko dry_run=1
dmesg | grep 'azahi-usb-overlay: PMGR'
rmmod azahi_usb_overlay
```

Compare the five printed values against the ones from the working boot. Any
domain whose actual field is not `0xf` on cold boot but was on the proxy boot
is the missing loader step.

## What the phone shows when this happens

Android USB preferences with "USB controlled by: This device" selected and
"Connected device: Couldn't switch" underneath. The phone only takes the host
role when nothing on the other end presents as a host. That is the cold-boot
refusal seen from the phone side: the Mac never became a host, so the phone
did, and a data-role swap is then rejected because no PD stack on the Mac
answers it. Unplugging the phone lets the retry above wake the controller with
an empty port; plugging back in after `USB_HOST_READY` gives the Mac the host
role at attach. On the phone pick "Connected device" first, then tethering.

## Deliberately not changed

- No blanket `Restart=on-failure`. A restart only helps the clean-refusal case;
  every other case either repeats identically or is latched. The script now
  exits 75 for exactly that case and the unit sets `RestartForceExitStatus=75`
  with `RestartSec=10` and no start limit, so the wake is retried every ten
  seconds until the port is empty and it succeeds. Each retry is the same
  read-only status probe the guard already does; nothing is written on a
  refusal. Bus faults, poison latches and identity mismatches still exit 1 and
  stay down.
- No change to `hpm-once.c`, `hpm-awake.h` or the overlay's power and DWC3
  preflight. The pinned tuple may well be too narrow for a cold boot, but
  widening it needs a fresh attended observation of the real cold-boot tuple,
  not a guess.
- No unit ordering change. Nothing in the script depends on NetworkManager or
  on a late mount.
