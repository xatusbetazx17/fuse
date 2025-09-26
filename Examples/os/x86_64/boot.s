BITS 32
SECTION .multiboot
align 4
    MULTIBOOT_MAGIC  equ 0x1BADB002
    MULTIBOOT_FLAGS  equ 0x0
    MULTIBOOT_CHECKSUM equ -(MULTIBOOT_MAGIC + MULTIBOOT_FLAGS)

    dd MULTIBOOT_MAGIC
    dd MULTIBOOT_FLAGS
    dd MULTIBOOT_CHECKSUM

SECTION .text
global _start
_start:
    cli
    mov esp, stack_top
    extern kmain
    call kmain
.hang:
    hlt
    jmp .hang

SECTION .bss
    resb 16384
stack_top:
