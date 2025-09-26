#include <stdint.h>
#include <stdbool.h>
#include "vga.h"
#include "gen_logic.h"  // generated from FUSE

static void kputs(const char* s) { vga_write_string(s); vga_write_string("\n"); }

void kmain(void) {
    vga_init();
    kputs("FUSE kernel online");
    // Call functions generated from FUSE
    const char* b = banner();
    int64_t m = meaning();
    int64_t z = add(20, 22);
    int64_t mx = max2(11, 17);
    int64_t d = demo_expr();

    vga_write_string("banner: "); vga_write_string(b); vga_write_string("\n");
    vga_write_string("meaning: "); vga_write_int(m); vga_write_string("\n");
    vga_write_string("add(20,22): "); vga_write_int(z); vga_write_string("\n");
    vga_write_string("max2(11,17): "); vga_write_int(mx); vga_write_string("\n");
    vga_write_string("demo_expr: "); vga_write_int(d); vga_write_string("\n");
    for(;;) { __asm__ __volatile__("hlt"); }
}
