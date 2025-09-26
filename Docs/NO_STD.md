# no_std with FUSE (via C backend)

This repo includes a path to **freestanding, no_std** builds for OS work:
- The C backend emits plain C with only `<stdint.h>` and `<stdbool.h>`.
- The OS example links **no libc** (see `CFLAGS` and linker script).
- Avoid heap, file IO, and syscalls in FUSE logic; stick to integers, booleans, const strings, and your own drivers.

**Guidelines**
- All local lets and function params/returns must be explicitly typed (C backend rule).
- No dynamic allocation in FUSE logic (add your own allocator in kernel C if needed).
- When you need platform features (ports, MMIO), write C stubs and call them from the kernel, or extend FUSE C backend with `@extern` shims (planned).

This is production‑style “no_std” using the C toolchain. The native LLVM backend will make this even cleaner in the future.
