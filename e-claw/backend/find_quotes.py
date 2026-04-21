#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys

file_path = sys.argv[1] if len(sys.argv) > 1 else "main.py"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

lines = content.split("\n")
for i, line in enumerate(lines):
    if '"""' in line:
        count = line.count('"""')
        prefix = line[:60].replace(chr(34), "'")
        print("Line %d: %d times - %s" % (i + 1, count, prefix))
