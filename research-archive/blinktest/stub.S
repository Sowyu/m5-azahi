// Breadcrumb stub, placed in the arm64 Image's unused PE-header area (0x40).
// Paints 64 rows RED then continues to primary_entry. x0 (DTB) is preserved and
// x1-x3 are re-zeroed as the boot protocol requires.
.section .text
.globl _stub
_stub:
    movz    x1, #0xc000             // fb 0x10fd310c000
    movk    x1, #0xd310, lsl #16
    movk    x1, #0x010f, lsl #32
    mov     x2, #64                 // 64 rows
    movz    x4, #0x2f40             // stride
1:  mov     x3, #3024
    mov     x5, x1
2:  movz    w6, #0x0000
    movk    w6, #0x3ff0, lsl #16    // red
    str     w6, [x5], #4
    subs    x3, x3, #1
    b.ne    2b
    add     x1, x1, x4
    subs    x2, x2, #1
    b.ne    1b
    mov     x1, #0                  // boot protocol: x1..x3 must be 0
    mov     x2, #0
    mov     x3, #0
    b       .                       // patched to primary_entry
