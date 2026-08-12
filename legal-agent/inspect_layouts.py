# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding="utf-8")

from pptx import Presentation

tpl = r"c:\Users\E0008090\Desktop\ESmart\Cursor方案\重庆PPT 模版1.pptx"
prs = Presentation(tpl)

for i, layout in enumerate(prs.slide_layouts):
    print(f"Layout {i}: {layout.name}")
