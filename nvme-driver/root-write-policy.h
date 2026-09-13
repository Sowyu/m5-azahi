/* SPDX-License-Identifier: GPL-2.0 */
/* Private J714s experiment. These bounds are NOT configurable parameters.
 * GPT root UUIDPRIVATE-LINUX-PARTUUID-NOT-CONFIGURED on the verified 4K SSD.
 * Shared verbatim with the host-side C boundary tests.
 */
#ifndef AZAHI_ROOT_WRITE_POLICY_H
#define AZAHI_ROOT_WRITE_POLICY_H
#if defined(__KERNEL__) && defined(AZAHI_ROOT_WRITES)
#error "Public reference only: independently audit storage boundaries before enabling writes"
#endif
#ifndef __KERNEL__
#include <stdbool.h>
#endif

#define AZAHI_ROOT_PARTUUID "PRIVATE-LINUX-PARTUUID-NOT-CONFIGURED"
#define AZAHI_ROOT_FIRST_LBA 204034123ULL
#define AZAHI_ROOT_END_LBA 242798667ULL /* exclusive */
#define AZAHI_ROOT_NSID 1U
#define AZAHI_ROOT_LBA_SHIFT 12U

enum azahi_root_request { AZAHI_OTHER, AZAHI_WRITE, AZAHI_FLUSH };
struct azahi_root_io {
	bool armed, passthrough;
	enum azahi_root_request request;
	unsigned int nsid, command_nsid, lba_shift, metadata_size;
	unsigned int opcode, flags, cdw2, cdw3, control, dsmgmt;
	unsigned int reftag, apptag, appmask, length;
	unsigned long long metadata, slba, bytes;
};

static inline bool azahi_root_io_allowed(const struct azahi_root_io *io)
{
	unsigned long long blocks;
	if (!io->armed || io->passthrough || io->nsid != AZAHI_ROOT_NSID ||
	    io->command_nsid != AZAHI_ROOT_NSID ||
	    io->lba_shift != AZAHI_ROOT_LBA_SHIFT || io->metadata_size ||
	    io->flags || io->cdw2 || io->cdw3 || io->metadata || io->dsmgmt ||
	    io->reftag || io->apptag || io->appmask)
		return false;
	/* Only a normal block flush, not a raw/passthrough command. NVMe flush
	 * has no address range; it drains this namespace's already queued writes.
	 * Upstream nvme_setup_flush() zeroes every unused command field.
	 */
	if (io->request == AZAHI_FLUSH)
		return io->opcode == 0 && !io->bytes && !io->slba &&
		       !io->length && !io->control;
	if (io->request != AZAHI_WRITE || io->opcode != 1 ||
	    (io->control & ~0xc000U) || io->length > 65535U)
		return false; /* only FUA and limited-retry control bits */
	blocks = (unsigned long long)io->length + 1;
	return io->bytes == (blocks << AZAHI_ROOT_LBA_SHIFT) &&
	       io->slba >= AZAHI_ROOT_FIRST_LBA &&
	       io->slba < AZAHI_ROOT_END_LBA &&
	       blocks <= AZAHI_ROOT_END_LBA - io->slba;
}
#endif
