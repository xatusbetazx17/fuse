ARCH=i386
CC=$(ARCH)-elf-gcc
LD=$(ARCH)-elf-ld
AS=nasm
CFLAGS=-ffreestanding -O2 -Wall -Wextra -m32 -fno-pic -fno-stack-protector -fno-builtin -nostdlib
LDFLAGS=-T link.ld -melf_i386

all: gen_logic.o kernel.elf iso

gen_logic.o: gen_logic.c gen_logic.h
	$(CC) $(CFLAGS) -c gen_logic.c -o gen_logic.o

kernel.o: kernel.c vga.h gen_logic.h
	$(CC) $(CFLAGS) -c kernel.c -o kernel.o

vga.o: vga.c vga.h
	$(CC) $(CFLAGS) -c vga.c -o vga.o

boot.o: boot.s
	$(AS) -f elf32 boot.s -o boot.o

kernel.elf: boot.o kernel.o vga.o gen_logic.o link.ld
	$(LD) $(LDFLAGS) -o kernel.elf boot.o kernel.o vga.o gen_logic.o

iso: kernel.elf
	mkdir -p iso/boot/grub
	cp kernel.elf iso/boot/kernel.elf
	echo 'set timeout=0' > iso/boot/grub/grub.cfg
	echo 'set default=0' >> iso/boot/grub/grub.cfg
	echo 'menuentry "FUSE" { multiboot /boot/kernel.elf }' >> iso/boot/grub/grub.cfg
	grub-mkrescue -o fuse.iso iso

run: iso
	qemu-system-i386 -cdrom fuse.iso

clean:
	rm -rf *.o *.elf iso fuse.iso
	rm -f gen_logic.c gen_logic.h
