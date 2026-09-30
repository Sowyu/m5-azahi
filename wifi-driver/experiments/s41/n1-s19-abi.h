/* Private verified S19 resource layout. */
struct old_table {
	__le64 address;
	__le32 length, reserved;
	__le64 end_address, end_length_reserved;
};
struct n1_alpha {
	struct pci_dev *pdev;
	void __iomem *bar;
	void *working;
	dma_addr_t dma;
	u64 old_dma_mask, old_coherent_mask;
	u16 old_command;
	atomic_t interrupts;
};
static_assert(sizeof(struct n1_alpha) == 56);
#define ALPHA_SIZE (2 * 1024 * 1024)
#define ALPHA_IRQS 16
struct old_boot {
	struct pci_dev *pdev;
	void __iomem *bar;
	void *image;
	dma_addr_t image_dma, table_dma;
	struct old_table *table;
	void *secondary;
	dma_addr_t secondary_dma;
	u8 expected_secondary_header[592];
	u64 old_dma_mask, old_coherent_mask;
	u16 old_command;
	atomic_t interrupts;
	void *context;
	dma_addr_t context_dma;
	void *messages, *cchi[2];
	dma_addr_t messages_dma, cchi_dma[2];
	u16 mtr_head, mcr_tail;
	struct n1_alpha *alpha;
};
static_assert(offsetof(struct old_boot, secondary) == 48);
static_assert(offsetof(struct old_boot, interrupts) == 676);
static_assert(offsetof(struct old_boot, context) == 680);
static_assert(offsetof(struct old_boot, messages) == 696);
static_assert(offsetof(struct old_boot, mtr_head) == 744);
static_assert(offsetof(struct old_boot, alpha) == 752);
static_assert(sizeof(struct old_boot) == 760);
#define CCHI_ALLOC_SIZE PAGE_ALIGN(16 * (16 + 1024))
#define SECONDARY_SIZE 11418624
