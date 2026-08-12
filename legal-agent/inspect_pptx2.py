# -*- coding: utf-8 -*-
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE
import io

src = r"c:\Users\E0008090\Desktop\ESmart\Cursor方案\2026-top-tech-trends-cn.pptx"
tpl = r"c:\Users\E0008090\Desktop\ESmart\Cursor方案\重庆PPT 模版1.pptx"

prs_src = Presentation(src)
prs_tpl = Presentation(tpl)

print("=== TEMPLATE LAYOUTS (detailed) ===")
for i, layout in enumerate(prs_tpl.slide_layouts):
    print(f"\nLayout {i}: {layout.name}")
    for ph in layout.placeholders:
        print(f"  PH idx={ph.placeholder_format.idx} type={ph.placeholder_format.type} name={ph.name!r}")

print("\n=== SOURCE SLIDE 1 ===")
slide1 = prs_src.slides[0]
for sh in slide1.shapes:
    print(f"  {sh.name} type={sh.shape_type} left={sh.left} top={sh.top} w={sh.width} h={sh.height}")
    if sh.has_text_frame:
        print(f"    text: {sh.text_frame.text!r}")

print("\n=== SOURCE IMAGE SLIDES sample ===")
for idx in [1, 2, 28]:
    slide = prs_src.slides[idx]
    for sh in slide.shapes:
        if sh.shape_type == MSO_SHAPE_TYPE.PICTURE:
            print(f"  Slide {idx+1}: img {sh.width.inches:.2f}x{sh.height.inches:.2f} at ({sh.left.inches:.2f},{sh.top.inches:.2f})")

print("\n=== TEMPLATE sample slide backgrounds ===")
for si, slide in enumerate(prs_tpl.slides):
    print(f"Slide {si+1} layout={slide.slide_layout.name}")
    for sh in slide.shapes:
        print(f"  {sh.name} type={sh.shape_type}")
