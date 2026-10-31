// SPDX-License-Identifier: GPL-2.0-only
/*
 * T6050 single-secondary observation test. Writes a stateless trap over unused
 * loader memory, releases exactly one core with Apple's CPU_START sequence and
 * records what is visible from CPU0. It never brings the core into Linux. The
 * core stays powered until the next machine reset; one run per boot.
 *
 * T2 separates what each release write does and whether a wake event changes
 * the status register, on one core or a whole cluster.
 * mode 1: +4 only, 2 ms, doorbell, 5 ms, fast IPI + SEV, 5 ms.
 * mode 2: as mode 1 with every non-boot core of the cluster in one mask.
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
#define FILL_BYTES	0x100000UL
#define STUB_OFF	0x100000UL
#define CRUMB_OFF	0x101000UL
#define SLED_BYTES	0xc000UL
#define CRUMB_MAGIC	0xa5a5c0deULL
#define MAX_SAMPLES	96

static int cpu = 1;
module_param(cpu, int, 0444);
static int mode = 1;
module_param(mode, int, 0444);

static const u32 stub[] = {
	0x10008000, 0xd2981bc2, 0xf2b4b4a2, 0xd53800a1, 0xa9000402, 0xf900081e,
	0xd5384243, 0xf9000c03, 0xd5033f9f, 0xd503209f, 0xd503205f, 0x17ffffff,
};

struct sample {
	u64 t, sts;
	u32 ps;
};
static struct sample samples[MAX_SAMPLES];

static int sample_for(void __iomem *cpu_sts, void __iomem *ps, u64 t0, u64 until,
		      int n, u64 *last_sts, u32 *last_ps)
{
	while (read_sysreg(cntpct_el0) - t0 < until) {
		u64 s = readq_relaxed(cpu_sts);
		u32 p = readl_relaxed(ps);

		if ((s != *last_sts || p != *last_ps) && n < MAX_SAMPLES) {
			samples[n++] = (struct sample){
				read_sysreg(cntpct_el0) - t0, s, p };
			*last_sts = s;
			*last_ps = p;
		}
	}
	return n;
}

static u64 impl_base(int c)
{
	return 0x210050000UL + ((u64)(c / 6) << 24) + ((u64)(c % 6) << 20);
}

static u32 bl_to(u64 from, u64 to)
{
	return 0x94000000 | (u32)(((s64)(to - from) >> 2) & 0x03ffffff);
}

static bool in_ram(u64 pa, u64 len)
{
	return region_intersects(pa, len, IORESOURCE_SYSTEM_RAM,
				 IORES_DESC_NONE) != REGION_DISJOINT;
}

static void fill_bl(void __iomem *map, u64 pa, u64 len, u64 target)
{
	u64 off;

	for (off = 0; off < len; off += 4)
		writel_relaxed(bl_to(pa + off, target), map + off);
}

static int __init t2_init(void)
{
	void __iomem *start, *cpu_sts, *ps, *lmap, *smap = NULL;
	u64 rvbar, base, stub_pa, sled_lo, sled_hi, t0, last_sts = ~0ULL, crumb[4];
	u32 last_ps = ~0U, before[5];
	unsigned long flags;
	int cluster = cpu / 6, core = cpu % 6, n = 0, i, ms;
	bool sled_ok;
	unsigned long global_mask;
	u32 core_mask;
	int mark[2];

	if (!of_machine_is_compatible("apple,j714s") || cpu < 1 || cpu > 17 ||
	    MIDR_PARTNUM(read_cpuid_id()) != 0x064) {
		pr_err("azahi-smp-t2: refused identity/cpu\n");
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
	stub_pa = base + STUB_OFF;
	sled_lo = read_sysreg_s(sys_reg(3, 0, 11, 1, 0));
	sled_hi = read_sysreg_s(sys_reg(3, 0, 11, 1, 1)) + 0x1000;
	if (!(rvbar & 1) || (base & 0x3fff) || base < 0x10000000000ULL ||
	    in_ram(base, LOADER_BYTES)) {
		pr_err("azahi-smp-t2: refused rvbar %#llx\n", rvbar);
		return -EINVAL;
	}
	sled_ok = sled_hi - sled_lo == SLED_BYTES && !in_ram(sled_lo, SLED_BYTES) &&
		  sled_lo > stub_pa && sled_hi - stub_pa < SZ_128M - SZ_1M;

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
		pr_err("azahi-smp-t2: refused, cpu%d not at rest ps=%#x start4=%#x\n",
		       cpu, readl_relaxed(ps), before[1]);
		return -EBUSY;
	}

	pr_info("azahi-smp-t2: cpu=%d base=%#llx rvbar=%#llx sled=%#llx..%#llx sled_trap=%d\n",
		cpu, base, rvbar, sled_lo, sled_hi, sled_ok);
	pr_info("azahi-smp-t2: original first words %#x %#x sled %#x\n",
		readl_relaxed(lmap), readl_relaxed(lmap + 0x800),
		sled_ok ? readl_relaxed(smap) : 0);

	memset_io(lmap + CRUMB_OFF, 0, 0x1000);
	for (i = 0; i < ARRAY_SIZE(stub); i++)
		writel_relaxed(stub[i], lmap + STUB_OFF + 4 * i);
	fill_bl(lmap, base, FILL_BYTES, stub_pa);
	if (sled_ok)
		fill_bl(smap, sled_lo, SLED_BYTES, stub_pa);
	dsb(sy);
	for (i = 0; i < ARRAY_SIZE(stub); i++)
		if (readl_relaxed(lmap + STUB_OFF + 4 * i) != stub[i]) {
			pr_err("azahi-smp-t2: stub readback mismatch\n");
			return -EIO;
		}
	if (readl_relaxed(lmap) != bl_to(base, stub_pa) ||
	    readl_relaxed(lmap + 0x7fc) != bl_to(base + 0x7fc, stub_pa)) {
		pr_err("azahi-smp-t2: fill readback mismatch\n");
		return -EIO;
	}
	pr_info("azahi-smp-t2: baseline sts=%#llx l2c sts=%#llx adr=%#llx inf=%#llx\n",
		readq_relaxed(cpu_sts), (u64)read_sysreg_s(sys_reg(3, 3, 15, 8, 0)),
		(u64)read_sysreg_s(sys_reg(3, 3, 15, 9, 0)),
		(u64)read_sysreg_s(sys_reg(3, 3, 15, 10, 0)));

	for (i = 0; i < 18; i++) {
		void __iomem *r = ioremap_np(impl_base(i) + 0x100, 8);

		if (r) {
			pr_info("azahi-smp-t2: rest cpu%d sts=%#llx\n", i, readq_relaxed(r));
			iounmap(r);
		}
	}
	/* Release in Apple's write order, with observation gaps between writes. */
	if (mode == 2) {
		global_mask = 0x3fUL << (6 * cluster);
		core_mask = 0x3f;
		if (cluster == 0) {
			global_mask &= ~1UL;
			core_mask &= ~1U;
		}
	} else {
		global_mask = BIT(cpu);
		core_mask = BIT(core);
	}
	local_irq_save(flags);
	t0 = read_sysreg(cntpct_el0);
	writel_relaxed(global_mask, start + 4);
	dsb(sy);
	n = sample_for(cpu_sts, ps, t0, 2000000, n, &last_sts, &last_ps);
	mark[0] = n;
	writel_relaxed(core_mask, start + 8 + 4 * cluster);
	dsb(sy);
	sev();
	n = sample_for(cpu_sts, ps, t0, 7000000, n, &last_sts, &last_ps);
	mark[1] = n;
	if (cluster == 0)
		write_sysreg_s(core, sys_reg(3, 5, 15, 0, 0));
	else
		write_sysreg_s(((u64)cluster << 16) | core, sys_reg(3, 5, 15, 0, 1));
	isb();
	sev();
	n = sample_for(cpu_sts, ps, t0, 12000000, n, &last_sts, &last_ps);
	local_irq_restore(flags);
	pr_info("azahi-smp-t2: samples=%d after+4=%d after_doorbell=%d masks %#lx %#x\n",
		n, mark[0], mark[1], global_mask, core_mask);

	for (i = 0; i < n; i++)
		pr_info("azahi-smp-t2: t=%lluns sts=%#llx ps=%#x\n", samples[i].t,
			samples[i].sts, samples[i].ps);

	for (ms = 0; ms < 2000; ms += 100) {
		dsb(sy);
		if (readq_relaxed(lmap + CRUMB_OFF) != 0)
			break;
		msleep(100);
	}
	for (i = 0; i < 4; i++)
		crumb[i] = readq_relaxed(lmap + CRUMB_OFF + 8 * i);

	if (crumb[0] == CRUMB_MAGIC)
		pr_info("azahi-smp-t2: ENTERED mpidr=%#llx landing=%#llx el=%#llx after %dms\n",
			crumb[1], crumb[2] - 4, crumb[3], ms);
	else
		pr_info("azahi-smp-t2: NO_ENTRY crumb=%#llx %#llx %#llx %#llx\n",
			crumb[0], crumb[1], crumb[2], crumb[3]);
	for (i = 0; i < 5; i++)
		pr_info("azahi-smp-t2: start+%#x %#x -> %#x\n", 4 * i, before[i],
			readl_relaxed(start + 4 * i));
	pr_info("azahi-smp-t2: final sts=%#llx ps=%#x l2c sts=%#llx adr=%#llx inf=%#llx\n",
		readq_relaxed(cpu_sts), readl_relaxed(ps),
		(u64)read_sysreg_s(sys_reg(3, 3, 15, 8, 0)),
		(u64)read_sysreg_s(sys_reg(3, 3, 15, 9, 0)),
		(u64)read_sysreg_s(sys_reg(3, 3, 15, 10, 0)));
	for (i = 0; i < 18; i++) {
		void __iomem *r = ioremap_np(impl_base(i) + 0x100, 8);
		void __iomem *q = ioremap_np(PMGR_BASE + 8 * i, 4);

		if (r && q) {
			pr_info("azahi-smp-t2: after cpu%d sts=%#llx ps=%#x\n", i,
				readq_relaxed(r), readl_relaxed(q));
		}
		if (r)
			iounmap(r);
		if (q)
			iounmap(q);
	}
	pr_info("azahi-smp-t2: end\n");

	/* Mappings stay valid only until return; a late core only touches DRAM. */
	if (smap)
		iounmap(smap);
	iounmap(lmap);
	iounmap(ps);
	iounmap(cpu_sts);
	iounmap(start);
	return -EAGAIN;
}
module_init(t2_init);
MODULE_DESCRIPTION("T6050 single-secondary observation test");
MODULE_LICENSE("GPL");
