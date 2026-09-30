/* Control ACIPC v3 layout derived from the installed AirshipDK's context
 * construction and t2026-CentauriControl.plist. Private experiment.
 * Context=104, peripheral info=16, four u16 index arrays, 16x16-byte MCR/MTR.
 * CR count=1, TR count=13. No descriptors are queued by this handshake.
 */
#define CTX_SIZE 0x68
#define PI_OFFSET 0x68
#define CR_HEAD 0x78
#define TR_TAIL 0x7a
#define CR_TAIL 0x94
#define TR_HEAD 0x96
#define MCR_OFFSET 0xb0
#define MTR_OFFSET 0x1b0
#define SCRATCH_OFFSET 0x2b0

static int prepare_context(struct n1_boot *n1)
{
	u8 *ctx;
	dma_addr_t base;
	struct iommu_domain *domain = iommu_get_domain_for_dev(&n1->pdev->dev);

	n1->context = dma_alloc_coherent(&n1->pdev->dev, PAGE_SIZE,
					&n1->context_dma, GFP_KERNEL);
	if (!n1->context)
		return -ENOMEM;
	ctx = n1->context;
	base = n1->context_dma;
	if (!IS_ALIGNED(base, PAGE_SIZE) ||
	    !iommu_iova_to_phys(domain, base) ||
	    !iommu_iova_to_phys(domain, base + PAGE_SIZE - 1))
		return -EFAULT;
	memset(ctx, 0, PAGE_SIZE);
	put_unaligned_le16(0x300, ctx + 0);
	put_unaligned_le16(CTX_SIZE, ctx + 2);
	put_unaligned_le64(base + PI_OFFSET, ctx + 0x08);
	put_unaligned_le64(base + CR_HEAD, ctx + 0x10);
	put_unaligned_le64(base + TR_TAIL, ctx + 0x18);
	put_unaligned_le64(base + CR_TAIL, ctx + 0x20);
	put_unaligned_le64(base + TR_HEAD, ctx + 0x28);
	put_unaligned_le16(1, ctx + 0x30);
	put_unaligned_le16(13, ctx + 0x32);
	put_unaligned_le64(base + MCR_OFFSET, ctx + 0x34);
	put_unaligned_le64(base + MTR_OFFSET, ctx + 0x3c);
	put_unaligned_le16(16, ctx + 0x44);
	put_unaligned_le16(16, ctx + 0x46);
	/* MTR doorbell vector 0; MCR has no doorbell. Interrupt vectors all 0.
	 * Headers/footers, out_of_order, in_place and scratch size all zero. */
	put_unaligned_le16(0xffff, ctx + 0x4a);
	put_unaligned_le64(base + SCRATCH_OFFSET, ctx + 0x58);
	put_unaligned_le32(2, ctx + PI_OFFSET);
	put_unaligned_le32(2, ctx + PI_OFFSET + 4);
	return 0;
}

static int wait_ipc(struct n1_boot *n1, u32 want)
{
	unsigned int i;
	u32 stage, status;
	for (i = 0; i < 2000; i++) {
		stage = readl(n1->bar + EXEC_STAGE);
		status = readl(n1->bar + 0x8050);
		if (stage != 2 || status > 2)
			return -EIO;
		if (status == want)
			return 0;
		usleep_range(1000, 1500);
	}
	return -ETIMEDOUT;
}

static int start_context(struct n1_boot *n1)
{
	int ret;
	if (readl(n1->bar + EXEC_STAGE) != 2 || readl(n1->bar + 0x8050) ||
	    readl(n1->bar + 0x8054) || readl(n1->bar + 0x8058))
		return -EBUSY;
	/* Module and all mappings are already pinned by firmware launch. */
	writel(1, n1->bar + 0x907c);
	ret = wait_ipc(n1, 1);
	if (ret)
		return ret;
	dma_wmb();
	writel(lower_32_bits(n1->context_dma), n1->bar + 0x8054);
	writel(upper_32_bits(n1->context_dma), n1->bar + 0x8058);
	writel(2, n1->bar + 0x907c);
	ret = wait_ipc(n1, 2);
	dma_rmb();
	dev_info(&n1->pdev->dev, "N1_CONTROL_INFO stage=%u ipc=%u sleep=%u field12=%u\n",
		get_unaligned_le32(n1->context + PI_OFFSET),
		get_unaligned_le32(n1->context + PI_OFFSET + 4),
		get_unaligned_le32(n1->context + PI_OFFSET + 8),
		get_unaligned_le32(n1->context + PI_OFFSET + 12));
	return ret;
}
