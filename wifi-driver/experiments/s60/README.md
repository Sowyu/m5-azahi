# S60: paired transmit-buffer alignment diagnostic

This experiment opens a separate native AC2/TID4 station queue in CR78/index194
and TR27. It requires the exact observed S49/S51/S58 state; it is not a general
startup module and must not be loaded with a batch of numbered experiments.

The root-only write endpoint accepts a one-byte alignment selector (0 or 2)
followed by a unicast Ethernet frame of 14–1514 bytes. The selector is removed
before submission. It changes the payload DMA address without inserting bytes
into the packet. The interface must be down, and at most twelve submissions are
accepted. Existing TX descriptors and footer encoding are unchanged.

A target W=1 build and non-launching preparation passed. Invalid alignment and
oversized writes were rejected without advancing submission counts. Three
identical-frame pairs, with Ethernet lengths 126, 826 and 1514 bytes, completed
with firmware status zero. Neither alignment delivered a packet to the helper;
the tethered control arrived. This is a negative diagnostic result, not a fix
or evidence of usable native Wi-Fi. The queue currently has six submissions
and six completions, with no reported failures.

Once launched, this module retains all published DMA until a normal reboot,
including error paths. Never force-unload it. A future reconnect must also ensure
this producer is stopped and this queue is drained. Do not reuse its ring slots
while it remains loaded. Only source and redacted results are published; the
live packet generator, addresses and observations remain private.
