# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding="utf-8")

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE, MSO_SHAPE
from pptx.util import Emu

src = r"c:\Users\E0008090\Desktop\ESmart\Cursor方案\2026-top-tech-trends-cn.pptx"
prs = Presentation(src)

print(f"Slides: {len(prs.slides)}")
print(f"Size: {prs.slide_width.inches:.2f} x {prs.slide_height.inches:.2f}")

for si, slide in enumerate(prs.slides):
    print(f"\n=== Slide {si+1} layout={slide.slide_layout.name} shapes={len(slide.shapes)} ===")
    for sh in slide.shapes:
        info = {
            "name": sh.name,
            "type": str(sh.shape_type).split("(")[0],
            "L": round(sh.left.inches, 2),
            "T": round(sh.top.inches, 2),
            "W": round(sh.width.inches, 2),
            "H": round(sh.height.inches, 2),
        }
        if sh.shape_type == MSO_SHAPE_TYPE.GROUP:
            info["children"] = len(sh.shapes)
        if sh.has_text_frame:
            txt = sh.text_frame.text.strip().replace("\n", " | ")
            if txt:
                info["text"] = txt[:120]
        if sh.shape_type == MSO_SHAPE_TYPE.PICTURE:
            info["img_ext"] = sh.image.ext
            info["img_size"] = f"{sh.image.size[0]}x{sh.image.size[1]}"
        if sh.shape_type == MSO_SHAPE_TYPE.AUTO_SHAPE:
            info["auto_shape"] = str(sh.auto_shape_type)
        if sh.is_placeholder:
            info["ph"] = sh.placeholder_format.type
        print(f"  {info}")
