#pragma once
#include <stdint.h>
void vga_init(void);
void vga_write_string(const char* s);
void vga_write_int(int64_t v);
