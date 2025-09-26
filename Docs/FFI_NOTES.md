# FFI Notes (C)

Until the FUSE compiler has first-class FFI syntax, use the C backend and regular linkage:

1. Write the C stub you want to call (e.g., `void outb(uint16_t port, uint8_t value);`).
2. Call those stubs from your kernel C (`kernel.c`). Your FUSE logic remains pure; the kernel coordinates with both.
3. If you want to call C **from FUSE-generated C**, a simple pattern is:
   - Put your prototypes in a header included by `kernel.c` *and* the generated translation unit.
   - Add a dummy FUSE declaration (planned: `@extern fn ...`) so the codegen can emit only a prototype.
   - For now, call C from the kernel side and pass values into FUSE functions.

A proper `@extern` in FUSE is on the roadmap; the design is straightforward in the C backend (emit prototype only).
