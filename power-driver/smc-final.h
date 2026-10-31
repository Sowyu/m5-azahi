/* SPDX-License-Identifier: GPL-2.0-only OR MIT */
/* Adapted from Asahi's macsmc atomic write. This shutdown-only path sends
 * one four-byte MBSE action, then lets the caller wait for power loss.
 * It deliberately does not drain/poll the RX mailbox: the stock poll can
 * loop indefinitely, and no reply is needed before hardware powers off.
 * Shared SMC state and lock remain owned by the installed core driver.
 */
static int smc_final_send(struct apple_smc *smc, u32 action)
{
	unsigned long irqflags;
	u64 msg;
	int ret;
	if (action != SMC_KEY(off1) && action != SMC_KEY(phra)) return -EINVAL;
	spin_lock_irqsave(&smc->lock, irqflags);
	if (smc->boot_stage != APPLE_SMC_INITIALIZED || !smc->atomic_mode ||
	    !smc->shmem.iomem || !IS_ALIGNED((unsigned long)smc->shmem.iomem, 4)) {
		ret = -EIO;
		goto out;
	}
	if (smc->atomic_pending) { ret = -EBUSY; goto out; }
	/* Exactly one 32-bit SRAM access; no wide copy on this M5 SMC. */
	writel(action, smc->shmem.iomem);
	smc->msg_id = (smc->msg_id + 1) & 15;
	msg = ((u64)SMC_KEY(MBSE) << 32) | (4u << 16) |
		(smc->msg_id << 12) | 0x11u;
	smc->atomic_pending = true;
	/* RTKit orders SRAM before mailbox MMIO. Atomic TX has a fixed timeout.
	 * On failure leave pending set: no cancellation or safe reuse is known.
	 */
	ret = apple_rtkit_send_message(smc->rtk, 0x20, msg, NULL, true);
out:
	spin_unlock_irqrestore(&smc->lock, irqflags);
	return ret;
}
