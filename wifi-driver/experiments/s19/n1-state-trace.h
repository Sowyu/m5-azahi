/* Read-only boot-stage mirrors, documented by GetConfigBootStage.
 * No sibling enable, DMA, reset, or MMIO. Print only state transitions.
 */
static void trace_n1_states(struct n1_boot *n1, const char *point)
{
    unsigned int f;
    u32 v;
    for (f = 0; f < 3; f++) {
        struct pci_dev *p = pci_get_slot(n1->pdev->bus, PCI_DEVFN(0, f));
        if (p) {
            if (!pci_read_config_dword(p, 0xf80, &v))
                dev_info(&n1->pdev->dev, "N1_SUBSYSTEM %s fn=%u stage=%u\n", point, f, v);
            pci_dev_put(p);
        }
    }
}
static void observe_n1_states(struct n1_boot *n1)
{
    u32 old[3] = { ~0U, ~0U, ~0U }, stage;
    unsigned int i, f;
    for (i = 0; i < 3000; i++) {
        for (f = 0; f < 3; f++) {
            struct pci_dev *p = pci_get_slot(n1->pdev->bus, PCI_DEVFN(0, f));
            if (!p)
                return;
            if (!pci_read_config_dword(p, 0xf80, &stage) && stage != old[f]) {
                dev_info(&n1->pdev->dev, "N1_SUBSYSTEM poll=%u fn=%u stage=%u\n", i, f, stage);
                old[f] = stage;
            }
            pci_dev_put(p);
        }
        if (old[0] == 3)
            break;
        usleep_range(10000, 11000);
    }
    dev_info(&n1->pdev->dev, "N1_SUBSYSTEM_TRACE_DONE polls=%u control=%u IRQ=%d\n", i, readl(n1->bar + EXEC_STAGE), atomic_read(&n1->interrupts));
}
