#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys

file_path = sys.argv[1] if len(sys.argv) > 1 else "main.py"

with open(file_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    count = line.count('"""')
    if count % 2 != 0:
        print("Line %d: %d times" % (i + 1, count))
        print("  %s..." % line[:50].replace('"', "'"))
