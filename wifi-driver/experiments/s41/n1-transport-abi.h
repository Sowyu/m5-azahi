/* Fresh S41 transport layout. Legacy prefix retained for bounded data companion. */
struct alpha_ipc { void *memory; dma_addr_t dma; struct n1_alpha *owner; };
struct alpha_restart { struct alpha_ipc shared; void *previous; u64 magic; };
struct rx_record { __le32 id, length; __le64 time_ns; u8 data[4096]; };
struct transport {
	struct alpha_ipc shared;
	struct alpha_restart *previous;
	struct pci_dev *pdev;
	void *pool;
	dma_addr_t dma;
	u64 magic;
	struct mutex io_lock, command_lock;
	struct delayed_work work;
	wait_queue_head_t wait;
	u16 mh, txhead, txtail, rxtail[7], rxhead[7];
	bool waiting, tx_done, response_done;
	u16 sequence, request_length;
	u32 cid;
	int command_result;
	u32 response_length;
	u8 response[4096];
	struct rx_record records[256];
};
