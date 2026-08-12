# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding="utf-8")

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE, PP_PLACEHOLDER

tpl = r"c:\Users\E0008090\Desktop\ESmart\Cursor方案\重庆PPT 模版1.pptx"
prs = Presentation(tpl)

for name in ["主KV", "上logo", "底图01", "底图02", "图片与标题", "仅标题"]:
    for layout in prs.slide_layouts:
        if layout.name == name:
            print(f"\n=== {name} ===")
            for sh in layout.shapes:
                ph = ""
                if sh.is_placeholder:
                    ph = f" PH_type={sh.placeholder_format.type}"
                print(f"  {sh.name} type={sh.shape_type}{ph} L={sh.left.inches:.2f} T={sh.top.inches:.2f} W={sh.width.inches:.2f} H={sh.height.inches:.2f}")
