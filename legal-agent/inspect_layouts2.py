# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding="utf-8")

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE

src = r"c:\Users\E0008090\Desktop\ESmart\Cursor方案\2026-top-tech-trends-cn.pptx"
tpl = r"c:\Users\E0008090\Desktop\ESmart\Cursor方案\重庆PPT 模版1.pptx"

prs_src = Presentation(src)
prs_tpl = Presentation(tpl)

# Check 底图01 layout slide in template
for si, slide in enumerate(prs_tpl.slides):
    if slide.slide_layout.name in ("底图01", "底图02", "主KV", "上logo"):
        print(f"\n=== Template demo slide: {slide.slide_layout.name} ===")
        print(f"Slide size: {prs_tpl.slide_width}, {prs_tpl.slide_height}")
        for sh in slide.shapes:
            print(f"  {sh.name} type={sh.shape_type} left={sh.left.inches:.2f} top={sh.top.inches:.2f} w={sh.width.inches:.2f} h={sh.height.inches:.2f}")
            if sh.has_text_frame:
                print(f"    text={sh.text_frame.text!r}")

# Check layout placeholders positions via adding temp slide
layout = None
for l in prs_tpl.slide_layouts:
    if l.name == "底图01":
        layout = l
        break

print("\n=== 底图01 layout shapes ===")
for sh in layout.shapes:
    print(f"  {sh.name} type={sh.shape_type} left={sh.left.inches:.2f} top={sh.top.inches:.2f} w={sh.width.inches:.2f} h={sh.height.inches:.2f}")

print("\n=== Source title ===")
for sh in prs_src.slides[0].shapes:
    if sh.has_text_frame and sh.text_frame.text.strip():
        print(repr(sh.text_frame.text))
