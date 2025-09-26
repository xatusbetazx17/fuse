# FUSE Systems Guide — Building a Minimal OS (x86, GRUB/Multiboot)

> This guide gives you a **working kernel skeleton** in C/ASM and shows how to **generate logic in FUSE** (compiled to C) and link it into the kernel. It’s a practical path from FUSE code to an OS you can boot in QEMU.

## Prerequisites
- Linux/macOS (Windows WSL works)
- `nasm`, `grub-mkrescue`, `xorriso`
- `i686-elf-gcc` (cross compiler) or `clang` configured for freestanding i386
- `qemu-system-i386`
- Python 3

## Layout
```
examples/os/x86_64/
  boot.s        # Multiboot1 header + 32-bit entry stub
  kernel.c      # kmain() calls into generated FUSE logic
  vga.c/.h      # simple VGA text-mode output
  link.ld       # linker script
  Makefile      # build + run
examples/os/logic.fuse  # your FUSE logic (compiled to gen_logic.c/.h)
tools/fusec.py          # FUSE→C codegen (alpha)
```

## 1) Generate C from your FUSE logic
```bash
cd examples/os
python ../../tools/fusec.py logic.fuse -o x86_64/gen_logic
```
This produces `x86_64/gen_logic.c` and `.h` (monomorphic C).

## 2) Build the kernel ISO
```bash
cd x86_64
make
make run    # boots in QEMU
```
You should see **"FUSE kernel online"** and values computed by your FUSE functions printed to the VGA text buffer.

## Notes
- The C backend is **alpha**: it supports a subset (monomorphic fns, explicit types, if/ops/calls/blocks).
- For OS code, **avoid heap and stdlib**; stick to integers, booleans, and const strings.
- As FUSE’s LLVM/Wasm backends mature, you’ll be able to target bare metal directly. For now, bridging via C is the pragmatic route.
