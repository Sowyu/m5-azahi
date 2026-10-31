// Stateless secondary entry trap. Reached through "bl" so x30 records the landing
// address + 4. Needs no stack and no prior core state.
entry:
  adr  x0, entry+0x1000
  movz x2, #0xc0de
  movk x2, #0xa5a5, lsl #16
  mrs  x1, mpidr_el1
  stp  x2, x1, [x0]
  str  x30, [x0, #16]
  mrs  x3, CurrentEL
  str  x3, [x0, #24]
  dsb  sy
  sev
1:
  wfe
  b    1b
