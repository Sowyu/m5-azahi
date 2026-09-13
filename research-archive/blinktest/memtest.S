// T6050 memory prober. m1n1 enters at offset 0, MMU off, x0 = DTB.
// Walks 0x1010A960000..0x10F4AB00000 (the ADT's carveout-free window) in
// 256 MB steps. Writes a magic, reads it back, and paints an 8-pixel-tall
// stripe per chunk that passes. If a chunk faults, the machine dies there and
// the number of stripes tells us exactly how far it got.
//   screen fills top-to-bottom = all 57 GiB is genuinely accessible
//   stops partway              = the ADT carveout map is incomplete
//   no stripes at all          = the very first chunk is bad
.section .text
.globl _start
_start:
    b       entry
    .long   0
    .quad   0
    .quad   0x100000
    .quad   0
    .quad   0, 0, 0
    .ascii  "ARM\x64"
    .long   0

entry:
    // x1 = framebuffer 0x10fd310c000
    movz    x1, #0xc000
    movk    x1, #0xd310, lsl #16
    movk    x1, #0x010f, lsl #32

    // paint whole screen dark (so stripes stand out)
    mov     x2, #1964
    movz    x4, #0x2f40
    mov     x7, x1
0:  mov     x3, #3024
    mov     x5, x7
1:  movz    w6, #0x0020
    str     w6, [x5], #4
    subs    x3, x3, #1
    b.ne    1b
    add     x7, x7, x4
    subs    x2, x2, #1
    b.ne    0b

    // x19 = test ptr = 0x1010A960000
    movz    x19, #0x0000
    movk    x19, #0x0a96, lsl #16
    movk    x19, #0x0101, lsl #32
    // x21 = end = 0x10F4AB00000
    movz    x21, #0x0000
    movk    x21, #0x4ab0, lsl #16
    movk    x21, #0x010f, lsl #32
    mov     x20, #0                     // chunk counter

chunk:
    cmp     x19, x21
    b.ge    done
    movz    x9, #0xbeef
    movk    x9, #0xdead, lsl #16
    str     x9, [x19]                   // write
    dsb     sy
    ldr     x10, [x19]                  // read back
    cmp     x9, x10
    b.ne    done                        // mismatch: stop, stripes show where

    // paint stripe: 8 rows starting at row = chunk*8
    mov     x11, x20
    lsl     x11, x11, #3                // row = chunk*8
    mul     x12, x11, x4                // row * stride
    add     x12, x1, x12                // stripe address
    mov     x13, #8                     // 8 rows
2:  mov     x3, #3024
    mov     x5, x12
3:  movz    w6, #0xff00
    movk    w6, #0x03ff, lsl #16        // bright stripe
    str     w6, [x5], #4
    subs    x3, x3, #1
    b.ne    3b
    add     x12, x12, x4
    subs    x13, x13, #1
    b.ne    2b

    add     x20, x20, #1
    movz    x14, #0x0000
    movk    x14, #0x1000, lsl #16       // +256 MB
    add     x19, x19, x14
    b       chunk

done:
4:  wfe
    b       4b
