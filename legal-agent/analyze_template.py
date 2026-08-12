# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding="utf-8")

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE

tpl = r"c:\Users\E0008090\Desktop\ESmart\Cursor方案\重庆PPT 模版1.pptx"
prs = Presentation(tpl)

print("=== Template layouts safe content zones ===")
for layout in prs.slide_layouts:
    print(f"\n[{layout.name}]")
    bg = None
    blocked = []
    for sh in layout.shapes:
        if sh.shape_type == MSO_SHAPE_TYPE.PICTURE:
            bg = sh
        elif sh.is_placeholder:
            blocked.append({
                "name": sh.name,
                "type": sh.placeholder_format.type,
                "L": round(sh.left.inches, 2),
                "T": round(sh.top.inches, 2),
                "W": round(sh.width.inches, 2),
                "H": round(sh.height.inches, 2),
            })
    for b in blocked:
        print(f"  PH {b}")
