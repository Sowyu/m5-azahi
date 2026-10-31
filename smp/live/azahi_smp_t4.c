// SPDX-License-Identifier: GPL-2.0-only
/*
 * T6050 single-secondary observation test. Writes a stateless trap over unused
 * loader memory, releases exactly one core with Apple's CPU_START sequence and
 * records what is visible from CPU0. It never brings the core into Linux. The
 * core stays powered until the next machine reset; one run per boot.
 *
 * Hypothesis T4: the status register tells a core executing our words from one
 * that never fetches them. Fills with a single instruction and needs no store:
 * word=0 spins with "b .", word=1 sits in "wfi". Run each on a separate boot and
 * compare the final status. A difference shows execution; identical values leave
 * "no fetch" and "status does not reflect this" both open.
 */
#include <linux/delay.h>
#include <linux/io.h>
#include <linux/ioport.h>
#include <linux/irqflags.h>
#include <linux/mm.h>
#include <linux/module.h>
#include <linux/of.h>
#include <asm/cputype.h>
#include <asm/sysreg.h>

#define PMGR_BASE	0x280600000UL
#define CPU_START	0x280688000UL
#define RVBAR_ADDR	GENMASK_ULL(41, 11)
#define LOADER_BYTES	0x110000UL
#define SLED_BYTES	0xc000UL
#define MAX_SAMPLES	96

static int cpu = 1;
module_param(cpu, int, 0444);
static int word;
module_param(word, int, 0444);

struct sample {
	u64 t, sts;
	u32 ps;
};
static struct sample samples[MAX_SAMPLES];

static u64 impl_base(int c)
{
	return 0x210050000UL + ((u64)(c / 6) << 24) + ((u64)(c % 6) << 20);
}

static bool in_ram(u64 pa, u64 len)
{
	return region_intersects(pa, len, IORESOURCE_SYSTEM_RAM,
				 IORES_DESC_NONE) != REGION_DISJOINT;
}

static void fill_word(void __iomem *map, u64 len, u32 insn)
{
	u64 off;

	for (off = 0; off < len; off += 4)
		writel_relaxed(insn, map + off);
}

static int __init t4_init(void)
{
	void __iomem *start, *cpu_sts, *ps, *lmap, *smap = NULL;
	u64 rvbar, base, sled_lo, sled_hi, t0, last_sts = ~0ULL;
	u32 last_ps = ~0U, before[5], insn;
	unsigned long flags;
	int cluster = cpu / 6, core = cpu % 6, n = 0, i, ms;
	bool sled_ok;

	if (!of_machine_is_compatible("apple,j714s") || cpu < 1 || cpu > 17 ||
	    MIDR_PARTNUM(read_cpuid_id()) != 0x064) {
		pr_err("azahi-smp-t4: refused identity/cpu\n");
		return -ENODEV;
	}
	rvbar = 0;
	{
		void __iomem *r = ioremap_np(impl_base(cpu), 8);

		if (!r)
			return -ENOMEM;
		rvbar = readq_relaxed(r);
		iounmap(r);
	}
	base = rvbar & RVBAR_ADDR;
	sled_lo = read_sysreg_s(sys_reg(3, 0, 11, 1, 0));
	sled_hi = read_sysreg_s(sys_reg(3, 0, 11, 1, 1)) + 0x1000;
	if (!(rvbar & 1) || (base & 0x3fff) || base < 0x10000000000ULL ||
	    in_ram(base, LOADER_BYTES)) {
		pr_err("azahi-smp-t4: refused rvbar %#llx\n", rvbar);
		return -EINVAL;
	}
	sled_ok = sled_hi - sled_lo == SLED_BYTES && !in_ram(sled_lo, SLED_BYTES);

	start = ioremap_np(CPU_START, 0x20);
	cpu_sts = ioremap_np(impl_base(cpu) + 0x100, 8);
	ps = ioremap_np(PMGR_BASE + 8 * cpu, 4);
	lmap = ioremap_wc(base, LOADER_BYTES);
	if (sled_ok)
		smap = ioremap_wc(sled_lo, SLED_BYTES);
	if (!start || !cpu_sts || !ps || !lmap || (sled_ok && !smap))
		return -ENOMEM;

	for (i = 0; i < 5; i++)
		before[i] = readl_relaxed(start + 4 * i);
	if (readl_relaxed(ps) != 0x100 || !(before[1] & BIT(cpu))) {
		pr_err("azahi-smp-t4: refused, cpu%d not at rest ps=%#x start4=%#x\n",
		       cpu, readl_relaxed(ps), before[1]);
		return -EBUSY;
	}

	pr_info("azahi-smp-t4: cpu=%d base=%#llx rvbar=%#llx sled=%#llx..%#llx sled_trap=%d\n",
		cpu, base, rvbar, sled_lo, sled_hi, sled_ok);
	pr_info("azahi-smp-t4: original first words %#x %#x sled %#x\n",
		readl_relaxed(lmap), readl_relaxed(lmap + 0x800),
		sled_ok ? readl_relaxed(smap) : 0);

	insn = word ? 0xd503207f : 0x14000000;
	fill_word(lmap, LOADER_BYTES, insn);
	if (sled_ok)
		fill_word(smap, SLED_BYTES, insn);
	dsb(sy);
	if (readl_relaxed(lmap) != insn || readl_relaxed(lmap + LOADER_BYTES - 4) != insn) {
		pr_err("azahi-smp-t4: loader fill readback mismatch\n");
		return -EIO;
	}
	if (sled_ok && (readl_relaxed(smap) != insn ||
			readl_relaxed(smap + SLED_BYTES - 4) != insn)) {
		pr_err("azahi-smp-t4: sled fill readback mismatch %#x %#x\n",
		       readl_relaxed(smap), readl_relaxed(smap + SLED_BYTES - 4));
		return -EIO;
	}
	pr_info("azahi-smp-t4: filled and verified word=%#x loader=%#lx sled=%d\n",
		insn, LOADER_BYTES, sled_ok);
	pr_info("azahi-smp-t4: baseline sts=%#llx l2c sts=%#llx adr=%#llx inf=%#llx\n",
		readq_relaxed(cpu_sts), (u64)read_sysreg_s(sys_reg(3, 3, 15, 8, 0)),
		(u64)read_sysreg_s(sys_reg(3, 3, 15, 9, 0)),
		(u64)read_sysreg_s(sys_reg(3, 3, 15, 10, 0)));

	/* Release: the same ordered writes as ApplePMGR::configMiscCores. */
	local_irq_save(flags);
	t0 = read_sysreg(cntpct_el0);
	writel_relaxed(BIT(cpu), start + 4);
	dsb(sy);
	writel_relaxed(BIT(core), start + 8 + 4 * cluster);
	dsb(sy);
	sev();
	while (read_sysreg(cntpct_el0) - t0 < 5000000) {
		u64 s = readq_relaxed(cpu_sts);
		u32 p = readl_relaxed(ps);

		if ((s != last_sts || p != last_ps) && n < MAX_SAMPLES) {
			samples[n++] = (struct sample){
				read_sysreg(cntpct_el0) - t0, s, p };
			last_sts = s;
			last_ps = p;
		}
	}
	local_irq_restore(flags);

	for (i = 0; i < n; i++)
		pr_info("azahi-smp-t4: t=%lluns sts=%#llx ps=%#x\n", samples[i].t,
			samples[i].sts, samples[i].ps);

	for (ms = 0; ms < 2000; ms += 500) {
		msleep(500);
		pr_info("azahi-smp-t4: %dms sts=%#llx ps=%#x\n", ms + 500,
			readq_relaxed(cpu_sts), readl_relaxed(ps));
	}
	for (i = 0; i < 5; i++)
		pr_info("azahi-smp-t4: start+%#x %#x -> %#x\n", 4 * i, before[i],
			readl_relaxed(start + 4 * i));
	pr_info("azahi-smp-t4: final sts=%#llx ps=%#x l2c sts=%#llx adr=%#llx inf=%#llx\n",
		readq_relaxed(cpu_sts), readl_relaxed(ps),
		(u64)read_sysreg_s(sys_reg(3, 3, 15, 8, 0)),
		(u64)read_sysreg_s(sys_reg(3, 3, 15, 9, 0)),
		(u64)read_sysreg_s(sys_reg(3, 3, 15, 10, 0)));
	pr_info("azahi-smp-t4: end\n");

	/* Mappings stay valid only until return; a late core only touches DRAM. */
	if (smap)
		iounmap(smap);
	iounmap(lmap);
	iounmap(ps);
	iounmap(cpu_sts);
	iounmap(start);
	return -EAGAIN;
}
module_init(t4_init);
MODULE_DESCRIPTION("T6050 single-secondary observation test");
MODULE_LICENSE("GPL");
