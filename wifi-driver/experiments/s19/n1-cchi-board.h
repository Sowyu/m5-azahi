/* Read-only CCHI board query used by CentauriBooter::getBoardParameters.
 * Response includes device identifiers. Save to root-only module parameter;
 * do not print its contents to the kernel log or publish the capture.
 */
#include <linux/hex.h>

static int board_result = -EINPROGRESS;
module_param(board_result, int, 0444);
static char board_data[133];
module_param_string(board_data, board_data, sizeof(board_data), 0400);

static int cchi_board(struct n1_boot *n1)
{
	u8 *tx = n1->cchi[0] + 1040, *rx = n1->cchi[1] + 1040;
	u8 *req = tx + 16, reply[66];
	u16 tx_tail, rx_tail;
	u32 length;
	unsigned int i;

	for (i = 3; i <= 4; i++)
		if (shared_index(n1->context, TR_HEAD + 2 * i) != 1 ||
		    shared_index(n1->context, TR_TAIL + 2 * i) != 1)
			return -EBUSY;
	if (readl(n1->bar + EXEC_STAGE) != 2 || readl(n1->bar + 0x8050) != 2)
		return -EIO;
	put_unaligned_le32(1024 << 8, rx);
	put_unaligned_le64(U64_MAX, rx + 4);
	put_unaligned_le32(1, rx + 12);
	dma_wmb();
	publish_index(n1->context, TR_HEAD + 8, 2);
	dma_wmb();
	writel(2, n1->bar + 0x9010);
	put_unaligned_le16(8, req);
	req[3] = 2; /* group0, opcode2, no payload */
	req[4] = 1; /* sequence after hello */
	put_unaligned_le32(2 | (8 << 8), tx);
	put_unaligned_le64(U64_MAX, tx + 4);
	put_unaligned_le32(1, tx + 12);
	dma_wmb();
	publish_index(n1->context, TR_HEAD + 6, 2);
	dma_wmb();
	writel(2, n1->bar + 0x900c);
	for (i = 0; i < 1000; i++) {
		if (readl(n1->bar + EXEC_STAGE) != 2 || readl(n1->bar + 0x8050) != 2)
			return -EIO;
		tx_tail = shared_index(n1->context, TR_TAIL + 6);
		rx_tail = shared_index(n1->context, TR_TAIL + 8);
		if (tx_tail > 2 || rx_tail > 2)
			return -EPROTO;
		if (tx_tail == 2 && rx_tail == 2) {
			dma_rmb();
			if (get_unaligned_le16(tx + 12) != 1 || get_unaligned_le16(rx + 12) != 1 ||
			    ((READ_ONCE(tx[15]) >> 1) & 7) != 2 ||
			    ((READ_ONCE(rx[15]) >> 1) & 7) != 2)
				return -EREMOTEIO;
			length = get_unaligned_le32(rx) >> 8;
			if (length != sizeof(reply))
				return -EMSGSIZE;
			memcpy(reply, rx + 16, sizeof(reply));
			if (get_unaligned_le16(reply) != sizeof(reply) ||
			    reply[2] || reply[3] != 2 || reply[4] != 1 || reply[5])
				return -EPROTO;
			bin2hex(board_data, reply, sizeof(reply));
			board_data[132] = 0;
			return 0;
		}
		usleep_range(1000, 1500);
	}
	return -ETIMEDOUT;
}
