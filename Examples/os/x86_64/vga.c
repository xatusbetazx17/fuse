#include "vga.h"

static volatile uint16_t* const VGA = (uint16_t*)0xB8000;
static int row = 0, col = 0;
static const int WIDTH = 80;
static const int HEIGHT = 25;
static uint8_t color = 0x0F; // white on black

static void putc(char c) {
    if (c == '\n') { row++; col = 0; return; }
    if (row >= HEIGHT) { row = 0; }
    VGA[row*WIDTH + col] = ((uint16_t)color << 8) | (uint8_t)c;
    col++;
    if (col >= WIDTH) { col = 0; row++; }
}

void vga_init(void) { row = 0; col = 0; }

void vga_write_string(const char* s) {
    while (*s) { putc(*s++); }
}

void vga_write_int(int64_t v) {
    char buf[32]; int i=0;
    if (v==0) { putc('0'); return; }
    if (v<0) { putc('-'); v = -v; }
    char tmp[32]; int n=0;
    while (v>0 && n<31) { tmp[n++] = '0' + (v%10); v/=10; }
    for (i=n-1;i>=0;i--) putc(tmp[i]);
}
