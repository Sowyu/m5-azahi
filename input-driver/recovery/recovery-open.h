/* SPDX-License-Identifier: GPL-2.0-only OR MIT */
/* Preserve the installed open semantics; permit one acknowledged startup
 * retry after a missing READY. Existing DMA allocations are never freed.
 */
static int recovery_open(struct hid_device *hdev)
{
	struct dchid_iface *iface = hdev->driver_data;
	bool recoverable;
	int ret;
	if (!iface || iface->hid != hdev || !iface->name) return -ENODEV;
	recoverable = iface->index == 1 && !strcmp(iface->name, "multi-touch");
	if (completion_done(&iface->ready)) goto ready;
	/* A previous open may have returned after its two-second READY timeout.
	 * Wait once more for a late success before considering another start.
	 */
	if (iface->starting && recoverable) {
		if (wait_for_completion_timeout(&iface->ready, msecs_to_jiffies(2000)))
			goto ready;
	} else {
		ret = original_start(iface);
		if (ret < 0) return ret;
		if (wait_for_completion_timeout(&iface->ready, msecs_to_jiffies(2000)))
			goto ready;
	}
	if (!recoverable || atomic_cmpxchg(&retry_used, 0, 1)) return -ETIMEDOUT;
	pr_warn("azahi-input: retrying trackpad startup once after READY timeout\n");
	ret = prepare_retry();
	if (ret) return ret;
	/* All start commands completed with ACK. This changes only the retry
	 * latch; the original driver retains firmware DMA and owns the reset.
	 */
	iface->starting = false;
	ret = original_start(iface);
	if (ret < 0) return ret;
	if (!wait_for_completion_timeout(&iface->ready, msecs_to_jiffies(2000))) {
		pr_err("azahi-input: retry failed; no further automatic firmware uploads\n");
		return -ETIMEDOUT;
	}
	pr_info("azahi-input: trackpad READY after bounded retry\n");
ready:
	iface->open = true;
	return 0;
}
