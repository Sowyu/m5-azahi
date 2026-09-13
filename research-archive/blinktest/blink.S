// Minimal arm64 "kernel" for T6050 handoff testing.
// m1n1 enters at offset 0, MMU off, x0 = DTB. This paints the framebuffer
// bright green and halts. If the screen changes, m1n1's handoff works and the
// problem is inside Linux. If it stays on the logo, the handoff itself is broken.
// Framebuffer from m1n1 boot_args: 0x10fd310c000, 3024x1964, stride 0x2f40, 30bpp

.section .text
.globl _start
_start:
    b       entry                   // code0 @0x00
    .long   0                       // code1 @0x04
    .quad   0                       // text_offset @0x08
    .quad   0x100000                // image_size @0x10
    .quad   0                       // flags @0x18
    .quad   0, 0, 0                 // reserved @0x20..0x37
    .ascii  "ARM\x64"               // magic @0x38
    .long   0                       // @0x3c

entry:                              // @0x40
    movz    x1, #0xc000             // 0x10fd310c000
    movk    x1, #0xd310, lsl #16
    movk    x1, #0x010f, lsl #32

    movz    x2, #1964               // rows
    movz    x4, #0x2f40             // stride (bytes)
1:  mov     x3, #3024               // cols
    mov     x5, x1
2:  movz    w6, #0xff00             // green, x2r10g10b10-ish
    movk    w6, #0x000f, lsl #16
    str     w6, [x5], #4
    subs    x3, x3, #1
    b.ne    2b
    add     x1, x1, x4
    subs    x2, x2, #1
    b.ne    1b

3:  wfe
    b       3b
