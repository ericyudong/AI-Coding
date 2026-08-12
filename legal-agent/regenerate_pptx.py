# -*- coding: utf-8 -*-
"""Regenerate source PPT using Chongqing template styling."""
from __future__ import annotations

import shutil
import sys
from io import BytesIO
from pathlib import Path

from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE_TYPE, PP_PLACEHOLDER
from pptx.enum.text import PP_ALIGN
from pptx.util import Emu, Inches, Pt

SRC = Path(r"c:\Users\E0008090\Desktop\ESmart\Cursor方案\2026-top-tech-trends-cn.pptx")
TPL = Path(r"c:\Users\E0008090\Desktop\ESmart\Cursor方案\重庆PPT 模版1.pptx")
OUT = Path(r"c:\Users\E0008090\Desktop\ESmart\Cursor方案\2026-top-tech-trends-cn-重庆模版.pptx")

COVER_TITLE = "2026年战略技术趋势"

# Content area on 上logo layout
CONTENT_LEFT = Inches(0.55)
CONTENT_TOP = Inches(2.65)
CONTENT_WIDTH = Inches(10.71)
CONTENT_HEIGHT = Inches(4.18)


def delete_all_slides(prs: Presentation) -> None:
    sld_id_lst = prs.slides._sldIdLst
    for sld_id in list(sld_id_lst):
        r_id = sld_id.rId
        prs.part.drop_rel(r_id)
        sld_id_lst.remove(sld_id)


def get_layout(prs: Presentation, name: str):
    for layout in prs.slide_layouts:
        if layout.name == name:
            return layout
    available = [layout.name for layout in prs.slide_layouts]
    raise ValueError(f"Layout '{name}' not found. Available: {available}")


def largest_picture_blob(slide) -> bytes | None:
    best = None
    best_area = 0
    for shape in slide.shapes:
        if shape.shape_type != MSO_SHAPE_TYPE.PICTURE:
            continue
        area = shape.width * shape.height
        if area > best_area:
            best_area = area
            best = shape.image.blob
    return best


def fit_picture_in_box(blob: bytes, box_left, box_top, box_width, box_height, slide):
    img = Image.open(BytesIO(blob))
    img_w, img_h = img.size
    scale = min(box_width / img_w, box_height / img_h)
    new_w = int(img_w * scale)
    new_h = int(img_h * scale)
    offset_x = int((box_width - new_w) / 2)
    offset_y = int((box_height - new_h) / 2)
    return slide.shapes.add_picture(
        BytesIO(blob),
        box_left + offset_x,
        box_top + offset_y,
        new_w,
        new_h,
    )


def add_cover_title(slide, title: str) -> None:
    left = Inches(1.77)
    top = Inches(2.66)
    width = Inches(11.77)
    height = Inches(1.21)
    textbox = slide.shapes.add_textbox(left, top, width, height)
    tf = textbox.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = title
    p.alignment = PP_ALIGN.CENTER
    run = p.runs[0]
    run.font.name = "微软雅黑"
    run.font.size = Pt(44)
    run.font.bold = True
    run.font.color.rgb = RGBColor(255, 255, 255)


def add_title_placeholder(slide, title: str) -> None:
    for shape in slide.placeholders:
        if shape.placeholder_format.type == PP_PLACEHOLDER.TITLE:
            shape.text = title
            for paragraph in shape.text_frame.paragraphs:
                for run in paragraph.runs:
                    run.font.name = "微软雅黑"
            return


def build_presentation() -> Path:
    if not SRC.exists():
        raise FileNotFoundError(f"Source not found: {SRC}")
    if not TPL.exists():
        raise FileNotFoundError(f"Template not found: {TPL}")

    shutil.copy2(TPL, OUT)
    prs = Presentation(str(OUT))
    src = Presentation(str(SRC))

    delete_all_slides(prs)

    # Cover slide
    cover_layout = get_layout(prs, "主KV")
    cover_slide = prs.slides.add_slide(cover_layout)
    add_cover_title(cover_slide, COVER_TITLE)

    # Content slides
    content_layouts = ["上logo", "底图01", "底图02"]
    src_slides = list(src.slides)

    for index, src_slide in enumerate(src_slides[1:], start=2):
        layout_name = content_layouts[(index - 2) % len(content_layouts)]
        layout = get_layout(prs, layout_name)
        slide = prs.slides.add_slide(layout)

        blob = largest_picture_blob(src_slide)
        if blob is None:
            continue

        if layout_name == "上logo":
            fit_picture_in_box(
                blob,
                CONTENT_LEFT,
                CONTENT_TOP,
                CONTENT_WIDTH,
                CONTENT_HEIGHT,
                slide,
            )
        else:
            # 底图01/02: place image in lower content region, keep template header visible
            fit_picture_in_box(
                blob,
                Inches(0.55),
                Inches(1.65),
                Inches(12.2),
                Inches(5.5),
                slide,
            )

    # Closing slide
    closing_layout = get_layout(prs, "仅标题")
    prs.slides.add_slide(closing_layout)

    prs.save(str(OUT))
    return OUT


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    out = build_presentation()
    prs = Presentation(str(out))
    print(f"Generated: {out}")
    print(f"Slides: {len(prs.slides)}")
    for i, slide in enumerate(prs.slides, start=1):
        print(f"  Slide {i}: {slide.slide_layout.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
