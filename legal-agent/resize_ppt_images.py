# -*- coding: utf-8 -*-
"""Resize slide images: fill content area but keep top-left logo zone clear."""
from __future__ import annotations

import sys
from pathlib import Path

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.util import Inches

PPT = Path(r"c:\Users\E0008090\Desktop\ESmart\Cursor方案\2026-top-tech-trends-cn-重庆模版.pptx")

SLIDE_W = 13.333333
SLIDE_H = 7.5

# Reserve top-left for template "赛力斯" branding (logo + header strip)
SAFE_TOP = 1.55
MARGIN_L = 0.35
MARGIN_R = 0.35
MARGIN_B = 0.30


def fit_below_logo(img_w: int, img_h: int) -> tuple[float, float, float, float]:
    """
    Maximize image within slide while:
    - top edge never above SAFE_TOP (protect 赛力斯 logo)
    - cover-style fill in the remaining region
    """
    box_l = MARGIN_L
    box_t = SAFE_TOP
    box_w = SLIDE_W - MARGIN_L - MARGIN_R
    box_h = SLIDE_H - SAFE_TOP - MARGIN_B

    aspect = img_w / img_h
    box_aspect = box_w / box_h

    if aspect >= box_aspect:
        # Wider image: fit height, may crop left/right
        h = box_h
        w = h * aspect
        left = box_l + (box_w - w) / 2
        top = box_t
    else:
        # Taller image: fit width, anchor top (may extend below bottom slightly)
        w = box_w
        h = w / aspect
        left = box_l
        top = box_t

    # Hard clamp: never overlap logo zone
    top = max(top, SAFE_TOP)
    return left, top, w, h


def resize_pictures() -> None:
    prs = Presentation(str(PPT))
    changed = 0

    for slide in prs.slides:
        for shape in slide.shapes:
            if shape.shape_type != MSO_SHAPE_TYPE.PICTURE:
                continue
            img_w, img_h = shape.image.size
            left, top, w, h = fit_below_logo(img_w, img_h)
            shape.left = Inches(left)
            shape.top = Inches(top)
            shape.width = Inches(w)
            shape.height = Inches(h)
            changed += 1

    prs.save(str(PPT))
    print(f"Updated {changed} pictures (logo safe zone: top >= {SAFE_TOP}\")")
    print(f"Saved: {PPT}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    resize_pictures()
