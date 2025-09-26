#include <stdio.h>
#include <stdint.h>
#include <stdbool.h>
#include "showcase.h"   // generated header

int main() {
    printf("entry_calc(6, 9) = %lld\n", (long long)entry_calc(6, 9));
    printf("entry_refs(10, 20) = %lld\n", (long long)entry_refs(10, 20));

    // Option[Int] roundtrip: we'll just print describe(flag)
    printf("describe(true) = %s\n", entry_describe(true));
    printf("describe(false) = %s\n", entry_describe(false));
    return 0;
}
