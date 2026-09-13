# Trackpad alternating-boot audit (M5 Pro / T6050 / J714s)

Read-only audit. No repo file was modified. All line numbers are against the
files as they exist at `the repo` right now.

## 0. Answer first

The most likely cause is **AFE hardware state surviving the reboot**. The
trackpad's analog front end is reset only by an SMC GPIO pulse that the MTP
firmware has to ask the host for. Nothing in Linux, the DT, or the loader ever
resets or power-gates that chip. A boot that succeeds leaves the AFE *running*,
so the next boot's `attach`/bootload finds a chip that is not in bootloader
mode and reports `Failed to attach to AFE` / `AFE Chip Boot Failure` /
`No HINT_L`. That failed boot leaves the AFE reset or idle, so the boot after
it succeeds. Period-2 alternation falls straight out of that, with no race
needed. Confidence: ~60% for this exact mechanism, ~85% that the cause is
carried hardware state rather than a driver encoding or timeout bug.

Making it worse, and the thing I would fix first: after one failure the driver
can never retry within that boot, because `iface->starting` is latched true.

---

## 1. Fork vs archive: no difference at all

`diff -u research-archive/input-driver/dockchannel-hid.c input-driver/dockchannel-hid.c`
is empty. Same for `test-power-request.py` and `build-module.sh`. The two
copies are byte-identical, so "earlier fork state" gives no extra signal.

### What the fork changes relative to upstream Asahi

Reconstructed from memory of upstream `drivers/hid/dockchannel-hid.c`:

- `dchid_reset_interface` (input-driver/dockchannel-hid.c:373-397) is the only
  real behavioural change. Upstream is the three-line body that sends
  `{0x40, 1, iface, state}` once. The fork adds a `apple,j714s`-only branch
  sending `{0x40, 2, iface, state, phase, 0,0,0,0}` twice, phase 0 then 1, and
  propagates the first error. The non-j714s path at line 396 is upstream verbatim.
- `#include "build/linux-7.0.13/drivers/hid/hid-ids.h"` and
  `HOST_VENDOR_ID_APPLE` (lines 21-23) are out-of-tree build plumbing.
- `dchid_enable_interface` (366-371), `dchid_request_gpio` (478-499),
  `dchid_handle_gpio` (890-943), the firmware path (399-476), the multi-touch
  start sequence (501-554) and `dockchannel_hid_remove`'s `BUG_ON(1)` (1214-1217)
  all match upstream. The `BUG_ON` is upstream Asahi's own code, not something
  this fork introduced.

So the fork is a very small delta, and the delta is in a path the logs show
already working (both power requests are accepted on failing boots too).

---

## 2. The recorded logs

Both traces come from `research-archive/input-driver/README.md:5-22`.

Successful native boot:

```text
1.769702  AZAHI_V2_POWER iface=1 state=0 accepted
1.876061  New AFE[0] cbor image received
2.013180  Touch MT ready
2.013191  AZAHI_V2_POWER iface=1 state=2 accepted
```

Failed native boot (`research-archive/input-driver/README.md:16-18`, detail at
lines 32-36 and 62-72):

```text
1.785445  AZAHI_V2_POWER iface=1 state=0 accepted
1.893409  New AFE[0] cbor image received
~1.9963   Failed to attach to AFE (-6) / AFE Chip Boot Failure / No HINT_L /
          AFE[0] bootload failed: 1
1.996471  AZAHI_V2_POWER iface=1 state=2 accepted
4.003073  iface multi-touch start timed out
          ...then repeated "Interface multi-touch is already starting"
```

Hypervisor PASS for comparison (`research-archive/input-driver/README.md:76-78`):
firmware send 21.434, OFF 21.449, CBOR 21.559, `Touch MT ready` 21.703, ON 21.708.

Three things fall out of those numbers.

**The AFE bootload happens inside the state=2 transaction.** OFF is acked in
under a millisecond; ON is acked 244 ms later (success) or 211 ms later
(failure), and in both traces the ON ack lands within microseconds of the
firmware's own verdict. `dchid_comm_cmd` is synchronous
(input-driver/dockchannel-hid.c:336), so the driver is sitting inside
`dchid_reset_interface(iface, 2)` holding `comm->out_mutex` for that entire
window.

**The driver's own timeouts never fire during the failure.** 211 ms is nowhere
near `COMMAND_TIMEOUT_MS 1000` (line 25). The 4.003073 timeout is
`START_TIMEOUT_MS 2000` (line 26) measured from the ON ack at 1.996471, i.e.
`dchid_open`'s wait at line 589 expiring 2.007 s later. It is a *consequence*
of the AFE failure, not a cause.

**The failing boot was the slower one.** OFF fires 16 ms *later* on the failed
boot than on the successful one, and CBOR-to-verdict is 103 ms on failure vs
137 ms on success. If more settling time helped, the later-starting boot would
be the one that worked. It isn't.

---

## 3. Hypotheses

### H1 — AFE/multitouch state carried across the reboot. LIKELY (primary)

Evidence for:

- **Nothing gates the power.** The MTP, dockchannel, SMC and dockchannel-hid
  nodes in `research-archive/t6050-j714s-hv-input.dts:26-88` have no
  `power-domains` property at all. `research-archive/t6050-pmgr.dtsi` contains
  no mtp/dockchannel/smc controller (grep finds only `dispext*` and the ANS
  group). `research-archive/t6050-j714s-native-ssd-ro.dts:2` says it outright:
  "No PMGR/reset providers: verified loader-prepared power stays unchanged."
- **`pd_ignore_unused` is in the native cmdline**
  (`research-archive/t6050-j714s-native-input.dts:7`), so genpd will not power
  anything down on the way out either.
- **The loader does not reset it.** `--prepare-mtp` is DAPF init only:
  `research-archive/probe/boot-input.py:136-139` calls
  `proxy.dapf_init("/arm-io/dart-mtp")` and nothing else. No power write, no
  reset. `--prepare-mtp-tunables` (lines 140-158) only writes DART tunables.
- **Shutdown never completes.** `research-archive/standalone-loader/README.md:13-15`:
  "systemctl poweroff stalls at poweroff.target, requiring manual hold-power."
  `PROGRESS.md:564-565` repeats it. Every cycle is a forced SoC reset with the
  SMC and its rails still up. The AFE sits behind the SMC, so it does not see
  a power cycle.
- **The driver never sends a power-OFF at shutdown.** There is no
  `.shutdown` callback and no PM ops on `dockchannel_hid_driver`
  (input-driver/dockchannel-hid.c:1226-1233). The only remove path is
  `BUG_ON(1)` (line 1216). `dchid_reset_interface(iface, 0)` is only ever
  reached from `dchid_start_interface` (line 541), i.e. on the way *up*.
- **The failure signature is "chip already running", not "chip absent".**
  `Failed to attach to AFE (-6)` comes *first*, then `AFE Chip Boot Failure`
  and `No HINT_L`. A chip that is powered and executing its application
  firmware will not answer a bootloader attach and will not raise HINT_L for a
  new bootload. A chip that is off or held in reset would fail differently.
- **Keyboard is unaffected on every boot**
  (`research-archive/PROGRESS.md:833-837`), which is exactly right: the
  keyboard interface has no `firmware-name`, so `dchid_get_firmware` returns
  early (lines 436-442), the whole `if (fw && size)` block at line 529 is
  skipped, and no AFE is involved.
- **The two HV passes were both after a fresh physical proxy boot**
  (`research-archive/PROGRESS.md:889-893`), i.e. the AFE had a different prior
  state each time. That is consistent with, not evidence against, H1.

Evidence against:

- Strictly circumstantial. Nobody has logged the AFE's pre-boot state, and
  there is no reproduction matrix (`research-archive/input-driver/README.md:19-21`
  says so explicitly). "Every second reboot" is a user impression over a small
  number of cycles.
- It assumes the *failing* boot leaves the AFE in a state the next boot likes.
  Plausible (the MTP firmware presumably drives reset or gives up with the
  chip held), but unverified.

### H2 — v2 power request ordering / double toggle. REFUTED

- The encoding is pinned by a compiled test.
  `input-driver/test-power-request.py:36-43` asserts, for state 0 and state 2,
  exactly two 9-byte packets `{0x40, 2, iface, state, phase, 0,0,0,0}` with
  phase 0 then 1, and lines 44-47 assert both error paths stop early. Line 49-51
  assert the old 4-byte form is unchanged for other boards.
- Order is OFF (state 0) then ON (state 2), matching
  `dchid_start_interface` lines 541-546, which is upstream's order.
- **It runs exactly once per boot.** `dchid_start_interface` is called only
  from `dchid_open` (line 585), guarded by `if (!completion_done(&iface->ready))`
  (line 584) and by `if (iface->starting)` (line 507). The failing boot's
  repeated `Interface multi-touch is already starting` lines
  (`research-archive/input-driver/README.md:68-69`) prove the guard held and
  no second toggle happened.
- Both power requests are accepted on failing boots too
  (`research-archive/input-driver/README.md:56-58`,
  `research-archive/CURRENT-STATE.md:80`), so the firmware is happy with the
  encoding on exactly the boots that fail.
- No delay between the phases, and none between OFF and ON. That is a real
  difference from anything Apple does, but it is identical on passing and
  failing boots, so it cannot be what alternates.

### H3 — GPIO not wired up. NOT the cause, but a genuine latent defect

The property name lines up correctly:

- `dchid_request_gpio` builds `snprintf(prop_name, ..., "apple,%s", iface->gpio_name)`
  (input-driver/dockchannel-hid.c:488) and calls
  `devm_gpiod_get_index(dev, prop_name, 0, GPIOD_OUT_LOW)` (line 490). gpiolib
  appends `-gpios`, so the lookup is `apple,afe-reset-gpios`.
- The DT provides exactly that:
  `research-archive/t6050-j714s-hv-input.dts:80-81`
  `apple,afe-reset-gpios = <&input_smc_gpio 0x1c 1>;` and
  `apple,stm-reset-gpios = <&input_smc_gpio 0x1d 1>;`, on the
  `apple,dockchannel-hid` node itself (line 69). Flags `1` = active low.
- That matches the reference ADT dumps byte for byte in layout:
  `research-archive/refdt/t6020-j414s.dts:1211-1212` and
  `research-archive/refdt/t6031-j514c.dts:847-848` both put the same two
  properties on the parent node.
- The native boot inherits these: `t6050-j714s-native-input.dts:2` includes
  `t6050-j714s-hv-input-sid0.dts`, which at line 3 includes
  `t6050-j714s-hv-input.dts`.
- Line 0x1c = 28 matches the pulse that was tried by hand:
  `research-archive/PROGRESS.md:843-845`, "SMC low GPIO controller, line 28".
- The macsmc GPIO driver is deliberately kept loaded. The blacklist in
  `research-archive/probe/build-native-input.py:51` and
  `build-native-ssdroot.py:190` is
  `macsmc_power,macsmc_input,macsmc_hwmon,rtc_macsmc`; core and GPIO are not in
  it, and `research-archive/CURRENT-STATE.md:891` says to "retain macsmc
  core/GPIO needed by the inputs".

So the GPIO is real and reachable. **But the probe-time deferral net is dead.**
`dockchannel_hid_probe` walks `for_each_child_of_node(dev->of_node, child)` and
looks for `apple,*-gpios` on the *children* (input-driver/dockchannel-hid.c:1143-1163).
The children are `multi-touch`, `keyboard`, `stm`, `actuator`, `tp_accel`
(t6050-j714s-hv-input.dts:82-87) and none of them carry a gpios property. The
loop therefore matches nothing, never returns `-EPROBE_DEFER`, and the comment
at lines 1137-1141 ("by then it's too late to defer") describes a guarantee the
code does not actually provide on this DT. This is upstream's bug too, and
upstream gets away with it because macsmc probes early. On a `maxcpus=1` box
with a hand-authored SMC node it is a live risk: if macsmc-gpio has not bound
when the MTP firmware sends `EVENT_GPIO_CMD` around 1.9 s, `devm_gpiod_get_index`
returns `-EPROBE_DEFER`, line 493 logs `Failed to request GPIO apple,afe-reset-gpios`,
and `dchid_handle_gpio` acks with `0xe000f00d` (line 894) so the AFE is never
pulsed. I rate this second, not first, because it explains intermittency but
not a clean period of two — and because if it were happening every other boot
we would already have seen the `Failed to request GPIO` line, if only anyone
had run an unfiltered dmesg.

Note also: `dchid_handle_gpio` runs on `comm->wq` and its ack goes through
`dchid_comm_cmd` -> `mutex_lock(&comm->out_mutex)` (line 939 -> line 323). That
mutex is held for the whole 200 ms+ `state=2` transaction. So if the firmware
asks for the AFE pulse during the ON request, the pulse itself still happens
promptly (lines 919-921, before the ack) but the *ack* is stalled until the ON
transaction finishes. Whether the MTP firmware tolerates that is unknown. Worth
watching in the logs; not something I would change blind.

### H4 — Timeouts under maxcpus=1. REFUTED

Covered in section 2. The failure is a firmware-reported AFE verdict 103 ms
after CBOR receipt, three orders below `COMMAND_TIMEOUT_MS 1000`
(line 25). `START_TIMEOUT_MS 2000` (line 26) fires at 4.003073, exactly 2.007 s
after the last successful command at 1.996471 — a downstream effect. And the
successful boot is the *earlier*, faster one. Software rendering and one CPU
are irrelevant here because everything happens before 2.1 s, long before KDE.

### H5 — `0xe00002c2`. Explained, and already fixed. Also: the prompt's guess is wrong.

`0xe00002c2` is **`kIOReturnBadArgument`**, not `kIOReturnNotReady`. IOKit
codes are `err_system(0x38) | sub_iokit_common | code`, giving the `0xe00002xx`
range with `kIOReturnError = 0x2bc`. Counting from there: `0x2bd` NoMemory,
`0x2be` NoResources, `0x2bf` IPCError, `0x2c0` NoDevice, `0x2c1` NotPrivileged,
**`0x2c2` BadArgument**. `kIOReturnNotReady` is `0x2d8`, and `kIOReturnTimeout`
is `0x2d6`.

That reading is confirmed by what happened next: the firmware rejected the
4-byte `{0x40, 1, iface, state}` request with BadArgument
(`research-archive/PROGRESS.md:840-842`), and switching to the 9-byte
will/has pair made it accepted on the first hardware run
(`research-archive/PROGRESS.md:766-769`). Malformed payload, correct error.
It says nothing about ordering or readiness, and it tells us nothing about the
current alternation, because those requests are now accepted on the failing
boots as well.

---

## 4. The bug that turns a transient failure into a whole ruined boot

Independent of root cause, and worth fixing on its own:

`dchid_start_interface` sets `iface->starting = true` at
input-driver/dockchannel-hid.c:514 and clears it **only on the `err:` path**
at line 552. The AFE failure does not take that path: all four power commands
succeed, so the function returns 0 at line 549 with `starting` still true.
`dchid_open` then times out at line 589-592 and returns `-ETIMEDOUT`. Every
subsequent `open()` hits the guard at line 507 and gets `-EINPROGRESS` plus a
`Interface multi-touch is already starting` warning. Nothing anywhere clears
the flag (grep: it appears at lines 160, 507, 508, 514, 552 and nowhere else).

That is exactly the behaviour recorded at `research-archive/PROGRESS.md:841-843`
("Opening /dev/input/event0 times out and later returns EINPROGRESS because
the interface remains marked starting") and the repeated warnings at
`research-archive/input-driver/README.md:68-69`.

If H1 is right, one in-boot retry would likely succeed for the same reason the
*next boot* succeeds: the failed attempt changes the AFE's state. So this one
flag is both the reason "every second reboot" is the observed granularity, and
the cheapest way to test H1.

---

## 5. (b) What to capture on the next failed boot

The single most useful thing: **run dmesg unfiltered.** Every previous capture
used a filter (`mtp|touch|dchid`, later `afe|touch mt|azahi_v2`) that excludes
all the GPIO lines, which is why we have never seen them
(`research-archive/input-driver/README.md:70-72` already flags this trap).

```sh
dmesg | grep -inE 'gpio|afe|hint|mtp|touch|iface|firmware|smc|input@|294b'
```

Then look for these, in this order:

1. `Requesting GPIO multi-touch#<id>: afe-reset` — driver line 485-486. Present
   means the firmware did ask for the AFE reset. **Absent on a failing boot
   while present on a passing one refutes H1 and points at the firmware not
   even trying to reset a chip it thinks is already up** (which is still H1's
   mechanism, one level down). Absent on *both* means the pulse never happens
   and H3 becomes primary.
2. `Failed to request GPIO apple,afe-reset-gpios` — driver line 493. Present on
   failing boots only **confirms H3** and refutes H1.
3. `GPIO command: multi-touch#<id>: 3` — driver line 914. Present with no
   preceding failure means the pulse was issued and H3 is dead.
4. `apple-smc`/`macsmc` bind messages and their timestamps vs the 1.87 s CBOR
   line. SMC binding *after* 1.9 s on the failing boot would confirm the
   probe-order race in H3.
5. `Failed to ACK GPIO command` — driver line 940, and any
   `Received unexpected flags`/`bad seq` (lines 1016, 1027). These would show
   the comm-mutex interleaving described in H3 actually biting.

Also worth one line: on a *passing* boot, `cat /sys/kernel/debug/gpio` (or
`gpioinfo`) before shutdown, to record the resting state of SMC line 0x1c. If
it differs from its state on a failing boot's early userspace, H1 is confirmed
directly.

---

## 6. (c) Minimal proposed change — UNTESTED

I am not proposing a new GPIO pulse. The one manual 10 ms pulse that was tried
"produced no readiness event" (`research-archive/PROGRESS.md:843-846`), the
required polarity and width are unknown, and getting it wrong can leave the AFE
held in reset and break the boots that currently work. That is a worse trade
than the symptom.

Instead: let the driver retry once, in-boot, which is the same recovery the
next reboot performs today. Four lines.

```diff
--- a/input-driver/dockchannel-hid.c
+++ b/input-driver/dockchannel-hid.c
@@ -157,6 +157,7 @@ struct dchid_iface {
 	uint8_t tx_seq;
 	bool deferred;
 	bool starting;
+	bool start_retried;
 	bool open;
 	struct completion ready;
 
@@ -586,8 +587,17 @@ static int dchid_open(struct hid_device *hdev)
 		if (ret < 0)
 			return ret;
 
 		if (!wait_for_completion_timeout(&iface->ready, msecs_to_jiffies(START_TIMEOUT_MS))) {
 			dev_err(iface->dchid->dev, "iface %s start timed out\n", iface->name);
+			/*
+			 * ponytail: one AFE bootload failure currently poisons the
+			 * whole boot, because dchid_start_interface() returned 0 and
+			 * left ->starting latched. Allow exactly one more attempt so
+			 * userspace can retry the open; drop this and drive
+			 * apple,afe-reset-gpios directly if the retry also fails.
+			 */
+			if (!iface->start_retried) {
+				iface->start_retried = true;
+				iface->starting = false;
+			}
 			return -ETIMEDOUT;
 		}
 	}
```

**Exact risk.** The retry re-runs `dchid_send_firmware` against an AFE in an
unknown state, and `dchid_send_firmware` uses `dmam_alloc_coherent`
(input-driver/dockchannel-hid.c:416), so the second attempt permanently leaks
one firmware-sized coherent DMA buffer — devm memory is only released on
unbind, and unbind is `BUG_ON(1)` (line 1216). That is why the retry is capped
at one and not left open. Secondary risk: if the MTP firmware dislikes a second
firmware upload in the same session it could hang the comm interface, which
would take the keyboard down with it, since everything shares
`comm->out_mutex` (line 323). Test this on a boot you are willing to lose, with
a known-good rollback image staged.

Expected outcome, and this is the point of the change: on a boot that would
have failed, the first `open()` returns `-ETIMEDOUT` and the second reaches
`Touch MT ready`. If it does, H1 is confirmed and the proper fix is an explicit
`afe-reset` pulse before `dchid_send_firmware`. If the retry fails identically,
H1 is wrong and the GPIO evidence from section 5 decides between H3 and
something new.

## 7. (d) Zero-behaviour-change fallback

If even the retry is too much for the next cycle, this changes nothing and
just makes the GPIO path visible. It is strictly additive logging.

```diff
--- a/input-driver/dockchannel-hid.c
+++ b/input-driver/dockchannel-hid.c
@@ -487,10 +487,12 @@ static int dchid_request_gpio(struct dchid_iface *iface)
 	snprintf(prop_name, sizeof(prop_name), "apple,%s", iface->gpio_name);
 
 	iface->gpio = devm_gpiod_get_index(iface->dchid->dev, prop_name, 0, GPIOD_OUT_LOW);
 
 	if (IS_ERR_OR_NULL(iface->gpio)) {
-		dev_err(iface->dchid->dev, "Failed to request GPIO %s-gpios\n", prop_name);
+		dev_err(iface->dchid->dev, "Failed to request GPIO %s-gpios: %ld\n",
+			prop_name, PTR_ERR(iface->gpio));
 		iface->gpio = NULL;
 		return -1;
 	}
 
+	dev_info(iface->dchid->dev, "Acquired GPIO %s-gpios\n", prop_name);
 	return 0;
 }
@@ -899,6 +901,9 @@ static void dchid_handle_gpio(struct dockchannel_hid *dchid, void *data, size_t
 	if (length < sizeof(*cmd))
 		return;
 
+	dev_info(dchid->dev, "GPIO event: iface=%d gpio=%d cmd=%d\n",
+		 cmd->iface, cmd->gpio, cmd->cmd);
+
 	if (cmd->iface >= MAX_INTERFACES || !(iface = dchid->ifaces[cmd->iface])) {
@@ -936,6 +941,8 @@ err:
 	ack->type = CMD_ACK_GPIO_CMD;
 	ack->retcode = retcode;
 	memcpy(ack->cmd, data, length);
 
+	dev_info(dchid->dev, "GPIO ack: retcode 0x%x\n", retcode);
+
 	if (dchid_comm_cmd(dchid, ack, sizeof(*ack) + length) < 0)
```

Distinguishing `PTR_ERR == -EPROBE_DEFER` (-517) from `-ENOENT` (-2) in that
first line separates "macsmc not up yet" from "DT property missing", which is
the whole of H3 in one number.

## 8. Loose end worth one line

`dockchannel_hid_probe`'s deferral pre-check scans the wrong node level
(input-driver/dockchannel-hid.c:1143 iterates children;
`research-archive/t6050-j714s-hv-input.dts:80-81` puts the gpios on the parent).
Changing that loop to also scan `dev->of_node`'s own properties would restore
the intended `-EPROBE_DEFER` guarantee. I left it out of the proposed diff
because it can turn a currently-booting configuration into an endlessly
deferring probe if the SMC never binds, and losing the keyboard is worse than
losing the trackpad.
