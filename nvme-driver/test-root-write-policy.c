/* Host-only tests of the exact policy compiled into the private module. */
#include <assert.h>
#include <limits.h>
#include <stdio.h>
#include "root-write-policy.h"

static unsigned long checks;
static void check(struct azahi_root_io io, bool expected)
{
	assert(azahi_root_io_allowed(&io) == expected);
	checks++;
}

int main(void)
{
	struct azahi_root_io good = {
		.armed = true, .request = AZAHI_WRITE,
		.nsid = 1, .command_nsid = 1, .lba_shift = 12,
		.opcode = 1, .slba = AZAHI_ROOT_FIRST_LBA, .bytes = 4096,
	}, io, flush;
	unsigned int n;
	assert(AZAHI_ROOT_FIRST_LBA * 4096 == 835723767808ULL);
	assert(AZAHI_ROOT_END_LBA * 4096 == 994503340032ULL);
	assert((AZAHI_ROOT_END_LBA - AZAHI_ROOT_FIRST_LBA) * 4096 == 158779572224ULL);
	check(good, true);
#define REJECT(field, value) do { io = good; io.field = (value); check(io, false); } while (0)
	REJECT(armed, false);
	REJECT(passthrough, true);
	REJECT(request, AZAHI_OTHER);
	REJECT(request, AZAHI_FLUSH);
	REJECT(nsid, 0); REJECT(nsid, 2); REJECT(nsid, 3); REJECT(nsid, UINT_MAX);
	REJECT(command_nsid, 0); REJECT(command_nsid, 2); REJECT(command_nsid, UINT_MAX);
	REJECT(metadata_size, 8); REJECT(metadata, 4096);
	REJECT(cdw2, 1); REJECT(cdw3, 1); REJECT(dsmgmt, 1);
	REJECT(reftag, 1); REJECT(apptag, 1); REJECT(appmask, 1);
	REJECT(bytes, 0); REJECT(bytes, 512); REJECT(bytes, 4095); REJECT(bytes, 4097);
	REJECT(bytes, ULLONG_MAX); REJECT(length, 65536);
	REJECT(slba, 0); REJECT(slba, ULLONG_MAX);
	/* GPT headers, all original partitions, EFI, helper and backup table. */
	{
		unsigned long long protected[] = {1, 2, 6, 140806, 180465551,
			203903051, 204034122, 242798667, 242831434,
			242965551, 244276260, 244276264};
		for (n = 0; n < sizeof(protected) / sizeof(protected[0]); n++)
			REJECT(slba, protected[n]);
	}
	for (n = 0; n < 256; n++) {
		io = good; io.opcode = n; check(io, n == 1);
		io = good; io.flags = n; check(io, n == 0);
		io = good; io.lba_shift = n; check(io, n == 12);
	}
	/* Every possible zero-based NVMe transfer length, both edges, overrun,
	 * wraparound, payload mismatch, and all possible control-bit patterns. */
	for (n = 0; n <= 65535; n++) {
		unsigned long long blocks = (unsigned long long)n + 1;
		io = good; io.length = n; io.bytes = blocks * 4096;
		check(io, true);
		io.slba = AZAHI_ROOT_FIRST_LBA - 1; check(io, false);
		io.slba = AZAHI_ROOT_END_LBA - blocks; check(io, true);
		io.slba++; check(io, false);
		io.slba = AZAHI_ROOT_END_LBA; check(io, false);
		io.slba = ULLONG_MAX - blocks + 1; check(io, false);
		io.slba = AZAHI_ROOT_FIRST_LBA; io.bytes++; check(io, false);
		io = good; io.control = n; check(io, !(n & ~0xc000U));
	}
	flush = (struct azahi_root_io) {
		.armed = true, .request = AZAHI_FLUSH,
		.nsid = 1, .command_nsid = 1, .lba_shift = 12,
	};
	check(flush, true);
	good = flush;
	REJECT(armed, false); REJECT(passthrough, true);
	REJECT(nsid, 2); REJECT(command_nsid, UINT_MAX);
	REJECT(request, AZAHI_OTHER); REJECT(request, AZAHI_WRITE);
	REJECT(bytes, 4096); REJECT(slba, AZAHI_ROOT_FIRST_LBA);
	REJECT(length, 1); REJECT(control, 0x4000); REJECT(flags, 1);
	REJECT(metadata, 4096); REJECT(metadata_size, 8);
	for (n = 0; n < 256; n++) {
		io = flush; io.opcode = n; check(io, n == 0);
	}
	printf("ROOT_WRITE_POLICY_PASS %lu checks\n", checks);
	return 0;
}
