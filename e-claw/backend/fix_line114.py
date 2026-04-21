#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys

file_path = "C:/eswin/emaas/AI-Coding/e-claw/backend/app/main.py"

with open(file_path, "rb") as f:
    data = f.read()

# Find line 114 and fix it
lines = data.split(b"\r\n")
# Line 114 is index 113
old_line = lines[113]
# Print the old line
print("Old line 114:", old_line)
# Replace the line - find the pattern ending with ?" and replace with ?"""
new_line = old_line.replace(b'?""', b'?"""')
lines[113] = new_line
print("New line 114:", new_line)

# Write back
with open(file_path, "wb") as f:
    f.write(b"\r\n".join(lines))
print("File fixed!")
