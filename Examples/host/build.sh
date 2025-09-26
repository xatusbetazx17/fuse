#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python tools/fusec.py examples/c_backend_showcase.fuse -o examples/host/showcase
cc -std=c11 -O2 -c examples/host/showcase.c -o examples/host/showcase.o
cc -std=c11 -O2 examples/host/driver.c examples/host/showcase.o -o examples/host/app
echo "Run: ./examples/host/app"
