/* SPDX-License-Identifier: MIT */
/* Private J714s one-core boot. No NVMe commands or persistent loader writes. */
#include "azahi_standalone.h"
#include "adt.h"
#include "dapf.h"
#include "kboot.h"
#include "memory.h"
#include "pmgr.h"
#include "smp.h"
#include "utils.h"
#include "xnuboot.h"
#include "libfdt/libfdt.h"
#include "tinf/tinf.h"

#define SAFE_LOW 0x1010a960000UL
#define SAFE_HIGH 0x10f4ab00000UL
#define KERNEL_ADDR 0x10800000000UL
#define INITRD_ADDR 0x10a00000000UL
#define KERNEL_BYTES 77398016U
#define INITRD_BYTES 70698084U

struct bundle_header {
    char magic[8];
    u32 version, args_len, dt_len, gzip_len, initrd_len;
    u32 args_crc, dt_crc, gzip_crc, initrd_crc;
} PACKED;

static int stop(const char *reason)
{
    printf("AZAHI_STANDALONE_STOP: %s; no kernel handoff\n", reason);
    return -1;
}

static bool reg_matches(const char *path, unsigned index, u64 base, u64 minimum_size)
{
    int trace[8];
    u64 address, length;
    return adt_path_offset_trace(adt, path, trace) >= 0 &&
           adt_get_reg(adt, trace, "reg", index, &address, &length) == 0 &&
           address == base && length >= minimum_size;
}

static int prepare_ans(void)
{
    static const char *names[] = {"FAB6_SOC", "APCIE_ST0", "ANS", "APCIE_SYS_ST0"};
    static const u64 addresses[] = {0x280900138, 0x280900128, 0x280900140, 0x280900150};
    u32 states[4];
    if (!reg_matches("/arm-io/ans", 0, 0x419600000, 0x48) ||
        !reg_matches("/arm-io/ans", 3, 0x41dcc0000, 0x1000) ||
        !reg_matches("/arm-io/ans", 9, 0x45dcc0000, 0x1000) ||
        !reg_matches("/arm-io/sart-ans", 0, 0x41dc50000, 0xc000))
        return stop("ANS/SART register identity");
    /* Resolve all names through the initialized ADT tables before MMIO. */
    for (unsigned i = 0; i < 4; i++)
        if (pmgr_lookup_device_addr(names[i]) != addresses[i])
            return stop("PMGR device identity");
    for (unsigned i = 0; i < 4; i++) {
        states[i] = read32(addresses[i]);
        printf("AZAHI_ANS_STATE %s=0x%x\n", names[i], states[i]);
        if (states[i] == 0xabad1dea ||
            (((states[i] >> 4) & 15) != 15 && !(i == 3 && states[i] == 0x1000030f)))
            return stop("unverified ANS parent/link state");
    }
    /* Check warm firmware before the sole permitted power-state write. */
    u32 running = read32(0x419600044);
    if (running == 0xabad1dea || !(running & 16))
        return stop("ANS firmware not running; no cold-reset fallback");
    if (((states[3] >> 4) & 15) != 15) {
        mask32(addresses[3], BIT(28) | BIT(9) | BIT(8) | 15, 15);
        bool ready = false;
        for (unsigned i = 0; i < 200; i++) {
            u32 value = read32(addresses[3]);
            if (value == 0xabad1dea)
                return stop("ANS link read fault");
            if (((value >> 4) & 15) == 15) {
                ready = true;
                break;
            }
            mdelay(10);
        }
        if (!ready)
            return stop("ANS link timeout");
    }
    printf("AZAHI_ANS_WARM_READY\n");
    return 0;
}

int azahi_standalone_run(void)
{
    const struct bundle_header *h = (void *)_payload_start;
    if (memcmp(h->magic, "AZAHI1\0\0", 8))
        return stop("no standalone bundle");
    const char *target = adt_getprop(adt, 0, "target-type", NULL);
    if (chip_id != T6050 || board_id != 8 || !target || strcmp(target, "J714s") ||
        !in_el2() || (mrs(MPIDR_EL1) & 0xffffff) != 0x40000)
        return stop("not J714s T6050 boot core at EL2");
    if (h->version != 1 || h->args_len < 1 || h->args_len > 4096 ||
        h->dt_len < 40 || h->dt_len > 65536 || h->gzip_len < 32 ||
        h->gzip_len > (32U << 20) || h->initrd_len != INITRD_BYTES)
        return stop("bundle bounds/version");
    u64 end = (u64)(h + 1) + h->args_len + h->dt_len + h->gzip_len + h->initrd_len;
    bool low_bundle = (u64)_base < SAFE_LOW && cur_boot_args.top_of_kernel_data < SAFE_LOW;
    bool high_test = (u64)_base == 0x10400000000UL &&
                     cur_boot_args.top_of_kernel_data < 0x10408000000UL;
    if (end > cur_boot_args.top_of_kernel_data || (!low_bundle && !high_test) ||
        cur_boot_args.phys_base >= SAFE_LOW ||
        cur_boot_args.phys_base + cur_boot_args.mem_size < SAFE_HIGH)
        return stop("payload or RAM outside tested layout");
    const char *args = (const char *)(h + 1);
    const void *fdt = args + h->args_len;
    const void *gz = (const u8 *)fdt + h->dt_len;
    const void *initrd = (const u8 *)gz + h->gzip_len;
    if (tinf_crc32(args, h->args_len) != h->args_crc ||
        tinf_crc32(fdt, h->dt_len) != h->dt_crc ||
        tinf_crc32(gz, h->gzip_len) != h->gzip_crc ||
        tinf_crc32(initrd, h->initrd_len) != h->initrd_crc)
        return stop("bundle CRC mismatch");
    if (args[h->args_len - 1] || strlen(args) != h->args_len - 1 ||
        !strstr(args, "azahi.ssd_root=1") || !strstr(args, "maxcpus=1") ||
        !strstr(args, "root=PARTUUID=PRIVATE-UUID-REMOVED") ||
        fdt_check_header(fdt) || fdt_totalsize(fdt) != h->dt_len ||
        fdt_node_check_compatible(fdt, 0, "apple,j714s"))
        return stop("boot arguments or DT identity");
    unsigned source_len = h->gzip_len, dest_len = KERNEL_BYTES;
    void *kernel = (void *)KERNEL_ADDR;
    if (tinf_gzip_uncompress(kernel, &dest_len, gz, &source_len) != TINF_OK ||
        dest_len != KERNEL_BYTES || source_len != h->gzip_len ||
        memcmp((u8 *)kernel + 0x38, "ARM\x64", 4) ||
        ((struct kernel_header *)kernel)->image_size != KERNEL_BYTES)
        return stop("kernel decode/header mismatch");
    printf("AZAHI_KERNEL_READY at %p bytes=%u\n", kernel, dest_len);
    dc_cvau_range(kernel, dest_len);
    ic_ivau_range(kernel, dest_len);
    kboot_set_initrd((void *)initrd, h->initrd_len);
    dc_cvau_range((void *)INITRD_ADDR, h->initrd_len);
    if (kboot_set_chosen("bootargs", args))
        return stop("cannot set bootargs");
    smp_set_wfe_mode(true);
    smp_start_secondaries(); /* J714s build initializes boot index then returns. */
    if (boot_cpu_idx != 0)
        return stop("unexpected boot CPU index");
    for (unsigned i = 1; i < 18; i++)
        if (smp_is_alive(i))
            return stop("secondary unexpectedly alive");
    if (prepare_ans() || dapf_init("/arm-io/dart-mtp", 1) || kboot_prepare_dt((void *)fdt))
        return stop("hardware/DT preparation failed");
    printf("AZAHI_STANDALONE_HANDOFF: fixed SSD root, one CPU\n");
    return kboot_boot(kernel);
}
