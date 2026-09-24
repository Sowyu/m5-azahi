# T6050 apcie0 Wi-Fi PCIe bring-up (Apple N1 / Centauri)

Experimental, default-off, untested on hardware. This describes the apcie0
root port, its DART and port 0 (the Apple N1 port, /arm-io/apcie0/pci-bridge0)
so Linux can enumerate the N1 functions 106b:1901 (control), 106b:1902
(alpha/WLAN) and 106b:1903 (beta/BT). The N1 protocol, firmware and WLAN driver
are a separate effort that builds on this. The SSD root is on the same
controller's storage fabric and must never be powered down or reset by this
work; see [the report](../docs/audit-2026-09-25/pcie.md) for the full analysis,
evidence and first-test plan.

## Files

- `gen-pcie-dt.py` generates the overlay from the Apple ADT JSON (the JSON that
  `ipsw dtree --json` produces). The repo cannot ship the ADT, so the script
  takes its path as an argument.
- `dts/t6050-j714s-pcie-wifi.dtso` the generated overlay, port 0 only. The
  sd-reader port (pci-bridge1) is left out.
- `test-pcie-dt.py` host test: checks the generated overlay against the ADT and
  the t6031 reference DT, then builds it with dtc and merges it onto a base DTB
  with fdtoverlay. Skips cleanly when the ADT JSON is absent.
- `pcie-apple-t6050.c` a small fork of the stock `pcie-apple.c` with a distinct
  `azahi,t6050-pcie` compatible and a link-timeout diagnostic. It adopts a link
  the loader already trained; it does not bring up the controller itself.
- `vendor/pcie-apple.original.c` the exact stock driver, for diffing.

The controller and port-0 register bring-up lives in the loader,
`standalone-loader/m1n1-20260911/src/azahi_pcie.c`, default off behind the
`azahi.pcie=probe` / `azahi.pcie=bringup` kernel cmdline gate.

## Generate and test

```sh
python3 gen-pcie-dt.py /path/to/j714s-adt.json -o dts/t6050-j714s-pcie-wifi.dtso
AZAHI_ADT_JSON=/path/to/j714s-adt.json python3 test-pcie-dt.py
```

Without the ADT the test still runs the reference-shape checks and skips the
rest. Building the overlay and merging needs `dtc`, `fdtoverlay` and `cpp`.

## Cross-compile the driver

Same recipe as the other drivers here: copy the source to a scratch dir with a
one-line Kbuild that adds the controller include path, then build against the
exact kernel.

```sh
printf 'obj-m := pcie-apple-t6050.o\nccflags-y += -I%s/drivers/pci/controller\n' "$KDIR" > Kbuild
make -C "$KDIR" M="$PWD" KBUILD_MODPOST_WARN=1 W=1 modules
```

Unresolved-symbol warnings are expected (no Module.symvers). Compile errors and
new warnings are not.

## How it is meant to boot

1. The loader (`azahi_pcie.c`, opt-in) enables only the GP-branch clocks, runs
   the GP PHY init and the port-0 register init, and stops at PORT_STATUS RUN.
   It refuses to run unless the SSD storage domains are already active, and it
   never touches or disables them.
2. Linux binds `pcie-apple-t6050` through the overlay, drives PERST# on GPIO 80,
   the refclk and LTSSM, and enumerates behind dart-apcie0 with SIDs 1, 2, 3.
3. The N1 chip still needs its power sequence (SMC key gP13, then the 'PrtC'
   port-control path). That is the N1 area's step; without it the link does not
   train and nothing enumerates.

## Open questions

- The apcie tunables (`apcie-common/phy/config-tunables`) live only in the live
  ADT; iBoot inserts them at boot and they are absent from the restore image.
  The loader reads them by name at runtime. Their values cannot be checked
  offline.
- Whether iBoot leaves the GP PHY and common fabric in the exact state the
  cold-boot path assumes. The `azahi.pcie=probe` dump answers this on the first
  session.
- The exact N1 endpoint power and reset ordering (owned by the N1 area).
- DBI link-width and max-speed tuning is intentionally skipped; the link may
  train at a default speed until that is added.
