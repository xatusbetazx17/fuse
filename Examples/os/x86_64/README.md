# Minimal OS Skeleton (x86, GRUB/Multiboot)

**What you get**
- 32‑bit GRUB‑bootable kernel (`kernel.elf`) that prints to VGA text buffer.
- Generated C code (`gen_logic.c/.h`) from your **FUSE** logic.

**Build**
```bash
# From examples/os
python ../../tools/fusec.py logic.fuse -o x86_64/gen_logic
cd x86_64
make
make run
```

If you don't have an `i386-elf` cross compiler, install one (Arch: `pacman -S i686-elf-gcc`; macOS: use `x86_64-elf` toolchain or use Docker).

**How it fits together**
- `logic.fuse` → `fusec.py` → `gen_logic.c/.h`
- `kernel.c` includes and calls your generated functions.
- `vga.c` writes directly to 0xB8000 to display text.

This is the easiest way to use FUSE on bare metal *today*. Later, a native LLVM backend can compile FUSE directly to ELF/PE and Wasm.
