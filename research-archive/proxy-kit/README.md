# m1n1 proxy kit — drive the M5 Pro from the M1 Pro over USB-C

**What this does to the M1 Pro: nothing.**
No install, no `sudo`, no drivers, no reboots, no security or boot changes.
The Python dependencies are vendored in `./lib` and everything runs off this
stick. Unplug it and no trace remains. All the modified-system work lives on
the M5, never on the borrowed machine.

## The one command you need (on the M1 Pro)

```
cd "/Volumes/Install macOS Sequoia/proxy-kit" && sh run.sh collect.py
```

## Order of operations (order matters)

1. Stick plugged into the **M1 Pro**.
2. **M5: shut down fully.** Hold the power button until "Loading startup
   options" appears. Pick **Linux** → Continue. Wait for the white log to stop
   at **`Running proxy...`**.
3. Connect the two Macs with a **DATA-capable** USB-C cable.
   On the M5 try a **left-side** port first; try the others if nothing appears.
4. On the M1 Pro: open Terminal, run the command above.

## What good looks like

```
Using device: /dev/cu.usbmodemPRIVATE_01      <- cable + ports are fine
CONNECTED.                              <- talking to the M5
AIC version reg @0x280400000 = 0x3...   <- reading live silicon
REAL ADT dumped: NNNNNN bytes           <- the prize
```

## It writes two files onto this stick

| File | What it is |
|---|---|
| `collect-report.txt` | Everything it read, plus any errors |
| `adt-real-t6050.bin` | The **real** device tree off the running M5 |

Claude reads both later — you never copy, retype, or photograph anything.

## Then come back

5. Eject the stick from the M1 Pro.
6. **M5:** hold power → pick **Macintosh HD** → normal macOS.
7. Plug the stick into the M5 and tell Claude **"read the report"**.

## Trouble

**`No /dev/cu.usbmodem* found`**
- Is the M5 actually sitting at `Running proxy...`? It may have slept — redo step 2.
- Try every USB-C port on the M5, then on the M1 Pro.
- Swap the cable. Charge-only cables fail silently — this is the #1 cause.

**"command line developer tools" dialog on the M1 Pro**
- **Cancel it.** Don't install anything on a machine that isn't yours.
  Tell Claude; the kit can ship its own Python instead.

**Anything hangs, or the M5 stops responding**
- Hold the power button to force it off. Nothing persists — m1n1 lives in RAM.

## Escape hatch, always

On the M5: hold the power button from a full shutdown → startup options →
**Macintosh HD**. This is firmware-level and works even if everything on disk
is broken.

## What's in here

| Path | Purpose |
|---|---|
| `run.sh` | Finds python3 + the M5's serial device, sets up paths, launches |
| `collect.py` | Connects, reads registers, dumps the device tree, writes the report |
| `proxyclient/` | m1n1's Python client (upstream) |
| `lib/` | Vendored `construct` + `pyserial` — why nothing needs installing |

Run `sh run.sh` with no arguments for an interactive Python shell instead
(`p` = proxy, `u` = utils). Reads are safe; avoid writing to random addresses.
