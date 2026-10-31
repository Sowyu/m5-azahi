// SPDX-License-Identifier: GPL-2.0-only
/*
 * Read-only T6050 CPU state snapshot. No writes to MMIO or system registers.
 * Every address below was read safely in earlier proxy sessions on this
 * machine, or is an architectural/identification register. It logs and refuses
 * to stay loaded, so each snapshot is a separate insmod.
 */
#include <linux/delay.h>
#include <linux/io.h>
#include <linux/module.h>
#include <linux/of.h>
#include <asm/cputype.h>
#include <asm/sysreg.h>

#define PMGR_BASE	0x280600000UL
#define CPU_START	0x280688000UL
#define CLUSTER_CTL	0x280620000UL
#define NR_T6050_CPUS	18

static u64 impl_base(int cpu)
{
	return 0x210050000UL + ((u64)(cpu / 6) << 24) + ((u64)(cpu % 6) << 20);
}

static u32 rd32(u64 pa)
{
	void __iomem *p = ioremap_np(pa & ~3UL, 4);
	u32 v;

	if (!p)
		return 0xdeadbeef;
	v = readl_relaxed(p);
	iounmap(p);
	return v;
}

static u64 rd64(u64 pa)
{
	void __iomem *p = ioremap_np(pa & ~7UL, 8);
	u64 v;

	if (!p)
		return 0xdeadbeefdeadbeefULL;
	v = readq_relaxed(p);
	iounmap(p);
	return v;
}

#define SYSREG(name, enc) \
	pr_info("azahi-smp-ro: %s=%#llx\n", name, (u64)read_sysreg_s(enc))

static int __init ro_init(void)
{
	static const u32 start_off[] = { 0x0, 0x4, 0x8, 0xc, 0x10 };
	static const u32 cpm_ps[] = { 0x90, 0x98, 0xa0 };
	int i;

	if (!of_machine_is_compatible("apple,j714s") ||
	    MIDR_IMPLEMENTOR(read_cpuid_id()) != 0x61 ||
	    MIDR_PARTNUM(read_cpuid_id()) != 0x064) {
		pr_err("azahi-smp-ro: refused, not J714s on the expected M core\n");
		return -ENODEV;
	}

	pr_info("azahi-smp-ro: snapshot begin midr=%#x mpidr=%#llx el=%#llx\n",
		read_cpuid_id(), read_cpuid_mpidr(), (u64)read_sysreg(CurrentEL));
	SYSREG("RVBAR_EL2", sys_reg(3, 4, 12, 0, 1));
	SYSREG("CTRR_C_LWR", sys_reg(3, 0, 11, 1, 0));
	SYSREG("CTRR_C_UPR", sys_reg(3, 0, 11, 1, 1));
	SYSREG("CTRR_C_CTL", sys_reg(3, 0, 11, 1, 4));
	SYSREG("L2C_ERR_STS", sys_reg(3, 3, 15, 8, 0));
	SYSREG("L2C_ERR_ADR", sys_reg(3, 3, 15, 9, 0));
	SYSREG("L2C_ERR_INF", sys_reg(3, 3, 15, 10, 0));

	for (i = 0; i < ARRAY_SIZE(start_off); i++)
		pr_info("azahi-smp-ro: CPU_START+%#x=%#x\n", start_off[i],
			rd32(CPU_START + start_off[i]));
	for (i = 0; i < 3; i++)
		pr_info("azahi-smp-ro: cluster_ctl[%d]=%#x apsc=%#llx\n", i,
			rd32(CLUSTER_CTL + 4 * i),
			rd64(0x210e20020UL + ((u64)i << 24)));
	for (i = 0; i < ARRAY_SIZE(cpm_ps); i++)
		pr_info("azahi-smp-ro: cpm_ps[%d]=%#x\n", i,
			rd32(PMGR_BASE + cpm_ps[i]));
	for (i = 0; i < NR_T6050_CPUS; i++)
		pr_info("azahi-smp-ro: cpu%d ps=%#x rvbar=%#llx\n", i,
			rd32(PMGR_BASE + 8 * i), rd64(impl_base(i)));
	pr_info("azahi-smp-ro: cpu0 sts=%#llx\n", rd64(impl_base(0) + 0x100));
	/* ACC ps: FAB*_ACC power state from the ADT device table, PMGR reads only. */
	pr_info("azahi-smp-ro: snapshot end\n");
	return -EAGAIN;
}
module_init(ro_init);
MODULE_DESCRIPTION("T6050 read-only CPU snapshot");
MODULE_LICENSE("GPL");
