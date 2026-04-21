#!/usr/bin/env python
# -*- coding: utf-8 -*-

file_path = "C:/eswin/emaas/AI-Coding/e-claw/backend/app/main.py"

with open(file_path, "rb") as f:
    data = f.read()

# Find line 636 and fix it
lines = data.split(b"\r\n")
# Line 636 is index 635
old_line = lines[635]
print("Old line 636:", old_line)

# The pattern ends with: ?])  (hex: 3f 5d 29)
# We need: ?"])  (hex: 3f 22 5d 29)
# So we insert 0x22 (a quote) before 0x5d (])
new_line = old_line.replace(b"?])", b'?"])')
lines[635] = new_line
print("New line 636:", new_line)

# Write back
with open(file_path, "wb") as f:
    f.write(b"\r\n".join(lines))
print("File fixed!")
