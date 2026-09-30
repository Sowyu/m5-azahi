/* Private ACIPC management experiment. All allocations are made before
 * firmware launch and remain pinned after any DMA exposure. BAR4 is unused.
 * Wire layout: AirshipDK tr_controller::open / transfer_queue / messenger.
 */
#define MANAGEMENT_COUNT 16
#define MESSAGE_SLOT_SIZE 128
#define CCHI_RING_BYTES (16 * (16 + 1024))
#define CCHI_ALLOC_SIZE PAGE_ALIGN(CCHI_RING_BYTES)

static int management_result = -EINPROGRESS;
module_param(management_result, int, 0444);
static unsigned int queues_opened;
module_param(queues_opened, uint, 0444);

static u16 shared_index(void *base, unsigned int offset)
{
	return le16_to_cpu(READ_ONCE(*(__le16 *)(base + offset)));
}

static void publish_index(void *base, unsigned int offset, u16 index)
{
	WRITE_ONCE(*(__le16 *)(base + offset), cpu_to_le16(index));
}

static bool management_mapping_valid(struct n1_boot *n1, dma_addr_t dma,
				     size_t size)
{
	struct iommu_domain *domain = iommu_get_domain_for_dev(&n1->pdev->dev);
	size_t offset;

	if (!domain || !IS_ALIGNED(dma, PAGE_SIZE) || !size ||
	    dma >= BIT_ULL(40) || size > BIT_ULL(40) - dma)
		return false;
	for (offset = 0; offset < size; offset += PAGE_SIZE)
		if (!iommu_iova_to_phys(domain, dma + offset))
			return false;
	return !!iommu_iova_to_phys(domain, dma + size - 1);
}

static int prepare_management(struct n1_boot *n1)
{
	unsigned int i;

	static_assert(MANAGEMENT_COUNT * MESSAGE_SLOT_SIZE <= PAGE_SIZE);
	n1->messages = dma_alloc_coherent(&n1->pdev->dev, PAGE_SIZE,
					 &n1->messages_dma, GFP_KERNEL);
	if (!n1->messages)
		return -ENOMEM;
	if (!management_mapping_valid(n1, n1->messages_dma, PAGE_SIZE))
		return -EFAULT;
	memset(n1->messages, 0, PAGE_SIZE);
	for (i = 0; i < ARRAY_SIZE(n1->cchi); i++) {
		n1->cchi[i] = dma_alloc_coherent(&n1->pdev->dev, CCHI_ALLOC_SIZE,
					       &n1->cchi_dma[i], GFP_KERNEL);
		if (!n1->cchi[i])
			return -ENOMEM;
		if (!management_mapping_valid(n1, n1->cchi_dma[i], CCHI_ALLOC_SIZE))
			return -EFAULT;
		memset(n1->cchi[i], 0, CCHI_ALLOC_SIZE);
	}
	return 0;
}

static void release_management(struct n1_boot *n1)
{
	unsigned int i;

	for (i = 0; i < ARRAY_SIZE(n1->cchi); i++)
		if (n1->cchi[i])
			dma_free_coherent(&n1->pdev->dev, CCHI_ALLOC_SIZE,
					  n1->cchi[i], n1->cchi_dma[i]);
	if (n1->messages)
		dma_free_coherent(&n1->pdev->dev, PAGE_SIZE,
				  n1->messages, n1->messages_dma);
}

static void build_cchi_open(u8 *message, unsigned int trid, dma_addr_t ring)
{
	memset(message, 0, MESSAGE_SLOT_SIZE);
	message[0] = 1; /* tr_open */
	message[2] = 16; /* 1024-byte footer: (16 * 4) << 4 */
	message[3] = 0x40;
	put_unaligned_le16(trid, message + 4);
	put_unaligned_le16(trid, message + 6);
	put_unaligned_le64(ring, message + 8);
	put_unaligned_le64(U64_MAX, message + 16);
	put_unaligned_le16(16, message + 24);
	put_unaligned_le16(0xffff, message + 26); /* in-place completion */
	put_unaligned_le16(trid, message + 28); /* ringdb vector */
	put_unaligned_le16(BIT(6), message + 30); /* only in_place set */
	/* priority, IRQ vector, interrupt moderation, accumulation = zero.
	 * Host doorbell timer settings are not transmitted in this message. */
}

static int wait_management_reply(struct n1_boot *n1, u16 tag)
{
	unsigned int attempt;
	u16 head = 0, tr_tail = 0;
	u8 completion[16], status, result;
	u32 length, word8;
	u16 count;
	bool counted;

	for (attempt = 0; attempt < 2000; attempt++) {
		if (readl(n1->bar + EXEC_STAGE) != 2 ||
		    readl(n1->bar + 0x8050) != 2)
			return -EIO;
		head = shared_index(n1->context, CR_HEAD);
		tr_tail = shared_index(n1->context, TR_TAIL);
		if (head >= MANAGEMENT_COUNT || tr_tail >= MANAGEMENT_COUNT)
			return -EPROTO;
		if (head != n1->mcr_tail) {
			dma_rmb();
			memcpy(completion, n1->context + MCR_OFFSET + n1->mcr_tail * 16, 16);
			status = completion[1];
			word8 = get_unaligned_le32(completion + 8);
			length = get_unaligned_le16(completion + 6) | ((word8 & 0xff) << 16);
			count = (word8 >> 8) & 0xffff;
			result = (status >> 1) & 7;
			counted = (status & 1) || result == 4;
			dev_info(&n1->pdev->dev,
				 "N1_MCR type=%#x status=%#x trid=%u tag=%u length=%u count=%u opaque=%#x cr_head=%u tr_tail=%u raw=%*phN\n",
				 completion[0], status, get_unaligned_le16(completion + 2),
				 get_unaligned_le16(completion + 4), length, count,
				 get_unaligned_le32(completion + 12), head, tr_tail, 16, completion);
			/* One outstanding command, no chains, no unsolicited event handling.
			 * Unknown descriptors are retained unchanged for offline diagnosis. */
			if ((completion[0] & 0x0c) || get_unaligned_le16(completion + 2) ||
			    get_unaligned_le16(completion + 4) != tag ||
			    (counted ? count != 1 : count != 0) || length > 52)
				return -EPROTO;
			if (result != 2 && result != 4)
				return -EREMOTEIO;
			n1->mcr_tail = (n1->mcr_tail + 1) % MANAGEMENT_COUNT;
			/* Finish all descriptor reads before returning the slot to firmware. */
			dma_mb();
			publish_index(n1->context, CR_TAIL, n1->mcr_tail);
			dma_wmb();
			return 0;
		}
		usleep_range(1000, 1500);
	}
	dev_err(&n1->pdev->dev, "N1_MTR_TIMEOUT head=%u tail=%u cr_head=%u cr_tail=%u irq=%d\n",
		n1->mtr_head, tr_tail, head, n1->mcr_tail, atomic_read(&n1->interrupts));
	return -ETIMEDOUT;
}

static int open_control_queues(struct n1_boot *n1)
{
	unsigned int i;
	u8 *message, *descriptor;
	u16 slot, tail, next;
	int ret;

	if (shared_index(n1->context, TR_HEAD) || shared_index(n1->context, TR_TAIL) ||
	    shared_index(n1->context, CR_HEAD) || shared_index(n1->context, CR_TAIL))
		return -EBUSY;
	for (i = 0; i < ARRAY_SIZE(n1->cchi); i++) {
		if (readl(n1->bar + EXEC_STAGE) != 2 || readl(n1->bar + 0x8050) != 2)
			return -EIO;
		slot = n1->mtr_head;
		next = (slot + 1) % MANAGEMENT_COUNT;
		tail = shared_index(n1->context, TR_TAIL);
		if (slot >= MANAGEMENT_COUNT || tail >= MANAGEMENT_COUNT || next == tail)
			return -EBUSY;
		message = n1->messages + slot * MESSAGE_SLOT_SIZE;
		build_cchi_open(message, 3 + i, n1->cchi_dma[i]);
		descriptor = n1->context + MTR_OFFSET + slot * 16;
		memset(descriptor, 0, 16);
		put_unaligned_le32(1 | (52 << 8), descriptor);
		put_unaligned_le64(n1->messages_dma + slot * MESSAGE_SLOT_SIZE, descriptor + 4);
		put_unaligned_le16(slot, descriptor + 12);
		dma_wmb();
		publish_index(n1->context, TR_HEAD, next);
		dma_wmb();
		writel(next, n1->bar + 0x9000);
		n1->mtr_head = next;
		dev_info(&n1->pdev->dev, "N1_TR_OPEN_SENT trid=%u tag=%u bytes=52 footer=1024 flags=0x40\n", 3 + i, slot);
		ret = wait_management_reply(n1, slot);
		if (ret)
			return ret;
		queues_opened++;
		dev_info(&n1->pdev->dev, "N1_TR_OPEN_ACK trid=%u\n", 3 + i);
	}
	return 0;
}
