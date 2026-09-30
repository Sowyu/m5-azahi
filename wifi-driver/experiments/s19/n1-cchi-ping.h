/* One bounded CCHI hello exchange. No radio commands or calibration writes.
 * CentauriBooter pingCheck uses gid=0, oid=0, payload "CentauriTransport\0".
 * HelperServices uses inline footer TX (kind2), empty footer RX (kind0).
 */
static int ping_result = -EINPROGRESS;
module_param(ping_result, int, 0444);

static int cchi_ping(struct n1_boot *n1)
{
	static const char hello[] = "CentauriTransport";
	u8 *tx = n1->cchi[0], *rx = n1->cchi[1];
	u8 *request = tx + 16, response[1024];
	u8 tx_status, rx_status;
	u16 tx_tail = 0, rx_tail = 0, total;
	u32 length;
	unsigned int i;

	static_assert(sizeof(hello) == 18);
	for (i = 3; i <= 4; i++)
		if (shared_index(n1->context, TR_HEAD + 2 * i) ||
		    shared_index(n1->context, TR_TAIL + 2 * i))
			return -EBUSY;
	if (readl(n1->bar + EXEC_STAGE) != 2 || readl(n1->bar + 0x8050) != 2)
		return -EIO;

	/* A receive descriptor offers the ring's own 1024-byte footer. */
	put_unaligned_le32(1024 << 8, rx);
	put_unaligned_le64(U64_MAX, rx + 4);
	put_unaligned_le32(0, rx + 12); /* tag0, no chain, initial status0 */
	dma_wmb();
	publish_index(n1->context, TR_HEAD + 2 * 4, 1);
	dma_wmb();
	writel(1, n1->bar + 0x9010);

	put_unaligned_le16(8 + sizeof(hello), request);
	/* group, opcode, sequence, status and reserved bytes all start at zero. */
	memcpy(request + 8, hello, sizeof(hello));
	put_unaligned_le32(2 | ((8 + sizeof(hello)) << 8), tx);
	put_unaligned_le64(U64_MAX, tx + 4);
	put_unaligned_le32(0, tx + 12);
	dma_wmb();
	publish_index(n1->context, TR_HEAD + 2 * 3, 1);
	dma_wmb();
	writel(1, n1->bar + 0x900c);
	dev_info(&n1->pdev->dev, "N1_CCHI_HELLO_SENT bytes=%zu gid=0 oid=0 seq=0 rx_capacity=1024\n",
		 8 + sizeof(hello));

	for (i = 0; i < 2000; i++) {
		if (readl(n1->bar + EXEC_STAGE) != 2 || readl(n1->bar + 0x8050) != 2)
			return -EIO;
		tx_tail = shared_index(n1->context, TR_TAIL + 2 * 3);
		rx_tail = shared_index(n1->context, TR_TAIL + 2 * 4);
		if (tx_tail > 1 || rx_tail > 1)
			return -EPROTO;
		if (tx_tail && rx_tail) {
			dma_rmb();
			tx_status = READ_ONCE(tx[15]);
			rx_status = READ_ONCE(rx[15]);
			length = get_unaligned_le32(rx) >> 8;
			dev_info(&n1->pdev->dev,
				 "N1_CCHI_COMPLETION tx_status=%#x rx_status=%#x length=%u tx=%*phN rx=%*phN\n",
				 tx_status, rx_status, length, 16, tx, 16, rx);
			if (get_unaligned_le16(tx + 12) || get_unaligned_le16(rx + 12) ||
			    ((tx_status >> 1) & 7) != 2 || ((rx_status >> 1) & 7) != 2)
				return -EREMOTEIO;
			if (length < 8 || length > sizeof(response))
				return -EMSGSIZE;
			memcpy(response, rx + 16, length);
			total = get_unaligned_le16(response);
			dev_info(&n1->pdev->dev,
				 "N1_CCHI_REPLY total=%u gid=%u oid=%u seq=%u status=%u header=%*phN\n",
				 total, response[2], response[3], response[4], response[5], 8, response);
			if (total != length || response[2] || response[3] || response[4])
				return -EPROTO;
			if (response[5])
				return -EREMOTEIO;
			dev_info(&n1->pdev->dev, "N1_CCHI_HELLO_OK payload_bytes=%u payload_prefix=%*phN\n",
				 length - 8, min_t(unsigned int, length - 8, 96), response + 8);
			return length > 8 ? 0 : -ENODATA;
		}
		usleep_range(1000, 1500);
	}
	dma_rmb();
	dev_err(&n1->pdev->dev, "N1_CCHI_TIMEOUT tx_tail=%u rx_tail=%u tx=%*phN rx=%*phN irq=%d\n",
		tx_tail, rx_tail, 16, tx, 16, rx, atomic_read(&n1->interrupts));
	return -ETIMEDOUT;
}
