#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
import ast

file_path = sys.argv[1] if len(sys.argv) > 1 else "main.py"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Count triple quotes
count = content.count('"""')
print(f"Triple quotes count: {count}")

# Check if odd
if count % 2 != 0:
    print("WARNING: Odd number of triple quotes!")

# Try to parse
try:
    ast.parse(content)
    print("Syntax OK!")
except SyntaxError as e:
    print(f"Syntax Error: {e}")
    # Find line numbers around the error
    lines = content.split("\n")
    if e.lineno:
        print(f"Error around line {e.lineno}")
        start = max(0, e.lineno - 5)
        end = min(len(lines), e.lineno + 5)
        for i in range(start, end):
            print(f"{i + 1}: {lines[i][:80]}")
