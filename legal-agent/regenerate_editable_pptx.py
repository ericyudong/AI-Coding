# -*- coding: utf-8 -*-
"""
Rebuild PPT with Chongqing template using editable elements extracted from source.
- Cover: native shapes from source slide 1
- Content slides: OCR text boxes + cropped diagram images (never full-page embed)
"""
from __future__ import annotations

import io
import shutil
import sys
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE_TYPE, PP_PLACEHOLDER
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt
from rapidocr_onnxruntime import RapidOCR

SRC_PPT = Path(r"c:\Users\E0008090\Desktop\ESmart\Cursor方案\2026-top-tech-trends-cn.pptx")
TPL = Path(r"c:\Users\E0008090\Desktop\ESmart\Cursor方案\重庆PPT 模版1.pptx")
OUT = Path(r"c:\Users\E0008090\Desktop\ESmart\Cursor方案\2026-top-tech-trends-cn-重庆模版-可编辑.pptx")

SLIDE_W = 13.333333
SLIDE_H = 7.5
CONTENT_L = 0.45
CONTENT_T = 1.35
CONTENT_W = SLIDE_W - 0.9
CONTENT_H = SLIDE_H - 1.9

OCR = RapidOCR()


def delete_all_slides(prs: Presentation) -> None:
    for sld_id in list(prs.slides._sldIdLst):
        prs.part.drop_rel(sld_id.rId)
        prs.slides._sldIdLst.remove(sld_id)


def get_layout(prs: Presentation, name: str):
    for layout in prs.slide_layouts:
        if layout.name == name:
            return layout
    raise ValueError(f"Layout not found: {name}")


def quad_to_rect(quad) -> tuple[float, float, float, float]:
    xs = [p[0] for p in quad]
    ys = [p[1] for p in quad]
    return min(xs), min(ys), max(xs), max(ys)


def px_to_slide(x0, y0, x1, y1, img_w, img_h):
    left = CONTENT_L + (x0 / img_w) * CONTENT_W
    top = CONTENT_T + (y0 / img_h) * CONTENT_H
    width = max(((x1 - x0) / img_w) * CONTENT_W, 0.2)
    height = max(((y1 - y0) / img_h) * CONTENT_H, 0.12)
    return left, top, width, height


def clamp_box(left, top, width, height):
    left = max(CONTENT_L, min(left, CONTENT_L + CONTENT_W - 0.15))
    top = max(CONTENT_T, min(top, CONTENT_T + CONTENT_H - 0.12))
    width = min(width, CONTENT_L + CONTENT_W - left)
    height = min(height, CONTENT_T + CONTENT_H - top)
    return left, top, max(width, 0.15), max(height, 0.12)


def overlaps(a, b, pad=0.06) -> bool:
    ax0, ay0, aw, ah = a
    bx0, by0, bw, bh = b
    return ax0 < bx0 + bw + pad and ax0 + aw + pad > bx0 and ay0 < by0 + bh + pad and ay0 + ah + pad > by0


def resolve_overlaps(items: list[dict]) -> list[dict]:
    placed: list[tuple] = []
    out = []
    for item in sorted(items, key=lambda x: (x["top"], x["left"])):
        left, top, width, height = item["left"], item["top"], item["width"], item["height"]
        rect = (left, top, width, height)
        n = 0
        while any(overlaps(rect, p) for p in placed) and n < 40:
            top += 0.1
            if top + height > CONTENT_T + CONTENT_H:
                top = max(CONTENT_T, CONTENT_T + CONTENT_H - height)
                break
            rect = (left, top, width, height)
            n += 1
        item = dict(item)
        item["left"], item["top"] = left, top
        placed.append((left, top, width, height))
        out.append(item)
    return out


def merge_line_items(items: list[dict]) -> list[dict]:
    """Merge OCR boxes on same horizontal band."""
    if not items:
        return items
    items = sorted(items, key=lambda x: (round(x["top"], 2), x["left"]))
    merged = [items[0]]
    for cur in items[1:]:
        prev = merged[-1]
        same_line = abs(cur["top"] - prev["top"]) < 0.15 and cur["left"] >= prev["left"] - 0.1
        if same_line:
            prev["text"] = prev["text"] + " " + cur["text"]
            prev["width"] = max(prev["left"] + prev["width"], cur["left"] + cur["width"]) - prev["left"]
            prev["height"] = max(prev["height"], cur["height"])
            prev["font_size"] = max(prev["font_size"], cur["font_size"])
        else:
            merged.append(cur)
    return merged


def is_footer(text: str) -> bool:
    t = text.strip()
    if len(t) <= 1:
        return True
    keys = ("Gartner", "gartner", "成为客户", "资料来源", "©")
    return any(k in t for k in keys) and len(t) < 80


def ocr_slide_image(img: Image.Image) -> list[dict]:
    buf = BytesIO()
    img.convert("RGB").save(buf, format="PNG")
    result, _ = OCR(buf.getvalue())
    if not result:
        return []

    w, h = img.size
    items = []
    for quad, text, score in result:
        if score < 0.5 or is_footer(text):
            continue
        x0, y0, x1, y1 = quad_to_rect(quad)
        left, top, width, height = px_to_slide(x0, y0, x1, y1, w, h)
        font_size = max(9, min((y1 - y0) / h * CONTENT_H * 72 * 0.75, 30))
        items.append(
            {
                "kind": "text",
                "text": text.strip(),
                "left": left,
                "top": top,
                "width": width,
                "height": height,
                "font_size": font_size,
                "bold": font_size >= 18,
                "src_top": top,
            }
        )
    items = merge_line_items(items)
    return resolve_overlaps(items)


def extract_diagrams(img: Image.Image, text_rects_px: list[tuple], max_ratio=0.62) -> list[Image.Image]:
    """Extract non-text visual regions as separate crops (not full slide)."""
    rgb = np.array(img.convert("RGB"))
    h, w = rgb.shape[:2]
    mask = np.zeros((h, w), dtype=bool)
    pad = max(6, int(min(w, h) * 0.012))
    for x0, y0, x1, y1 in text_rects_px:
        mask[
            max(0, int(y0) - pad) : min(h, int(y1) + pad),
            max(0, int(x0) - pad) : min(w, int(x1) + pad),
        ] = True

    gray = np.mean(rgb, axis=2)
    color_std = np.std(rgb, axis=2)
    content = (~mask) & (gray < 245) & (color_std > 8)
    if content.sum() < h * w * 0.04:
        return []

    labeled = content.astype(np.uint8)
    # simple connected components via scipy if available, else bounding box clusters
    try:
        from scipy import ndimage

        labeled, n = ndimage.label(content)
        crops = []
        for i in range(1, n + 1):
            ys, xs = np.where(labeled == i)
            if len(xs) < 80:
                continue
            x0, x1 = xs.min(), xs.max()
            y0, y1 = ys.min(), ys.max()
            area = (x1 - x0) * (y1 - y0)
            if area < h * w * 0.03 or area > h * w * max_ratio:
                continue
            crops.append(img.crop((x0, y0, x1 + 1, y1 + 1)))
        return crops[:4]
    except ImportError:
        ys, xs = np.where(content)
        x0, x1 = xs.min(), xs.max()
        y0, y1 = ys.min(), ys.max()
        area = (x1 - x0) * (y1 - y0)
        if area < h * w * 0.03 or area > h * w * max_ratio:
            return []
        return [img.crop((x0, y0, x1 + 1, y1 + 1))]


def choose_layout(text_count: int, diagram_count: int) -> str:
    if text_count <= 2 and diagram_count == 0:
        return "下标题"
    if diagram_count >= 1 and text_count <= 6:
        return "图片与标题"
    if text_count >= 12:
        return "标题和竖排文字"
    return "上logo"


def fill_title(slide, title: str) -> None:
    for ph in slide.placeholders:
        if ph.placeholder_format.type == PP_PLACEHOLDER.TITLE:
            ph.text = title[:100]
            for p in ph.text_frame.paragraphs:
                for r in p.runs:
                    r.font.name = "微软雅黑"
            return


def add_text(slide, item: dict) -> None:
    l, t, w, h = clamp_box(item["left"], item["top"], item["width"], item["height"])
    box = slide.shapes.add_textbox(Inches(l), Inches(t), Inches(w), Inches(h))
    tf = box.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.TOP
    p = tf.paragraphs[0]
    p.text = item["text"]
    run = p.runs[0]
    run.font.name = "微软雅黑"
    run.font.size = Pt(item["font_size"])
    run.font.bold = item.get("bold", False)
    run.font.color.rgb = RGBColor(33, 33, 33)


def place_diagrams(slide, crops: list[Image.Image], existing: list[dict]) -> None:
    if not crops:
        return
    n = len(crops)
    gap = 0.15
    if n == 1:
        slots = [(CONTENT_L + 4.5, CONTENT_T + 0.2, 7.0, CONTENT_H - 0.3)]
    else:
        col_w = (CONTENT_W - gap) / 2
        slots = [
            (CONTENT_L, CONTENT_T + 0.5, col_w, CONTENT_H - 0.8),
            (CONTENT_L + col_w + gap, CONTENT_T + 0.5, col_w, CONTENT_H - 0.8),
        ]
    for crop, (sl, st, sw, sh) in zip(crops[: len(slots)], slots):
        cw, ch = crop.size
        scale = min(sw / (cw / 96), sh / (ch / 96)) * 0.95
        w_in = (cw / 96) * scale
        h_in = (ch / 96) * scale
        left = sl + (sw - w_in) / 2
        top = st + (sh - h_in) / 2
        rect = (left, top, w_in, h_in)
        if any(overlaps(rect, (e["left"], e["top"], e["width"], e["height"])) for e in existing):
            left = CONTENT_L + 5.5
            top = CONTENT_T + 0.3
        buf = BytesIO()
        crop.save(buf, format="PNG")
        slide.shapes.add_picture(buf, Inches(left), Inches(top), Inches(w_in), Inches(h_in))


def build_cover(prs: Presentation, src_prs: Presentation) -> None:
    slide = prs.slides.add_slide(get_layout(prs, "主KV"))
    src = src_prs.slides[0]
    for shape in src.shapes:
        if shape.shape_type == MSO_SHAPE_TYPE.PICTURE and shape.width.inches < SLIDE_W * 0.5:
            top = shape.top
            if top.inches < 0:
                top = Inches(0.15)
            slide.shapes.add_picture(
                BytesIO(shape.image.blob), shape.left, top, shape.width, shape.height
            )
        elif shape.has_text_frame and shape.text_frame.text.strip():
            tx = slide.shapes.add_textbox(shape.left, shape.top, shape.width, shape.height)
            tx.text_frame.text = shape.text_frame.text.strip()
            for p in tx.text_frame.paragraphs:
                for r in p.runs:
                    r.font.name = "微软雅黑"
                    if not r.font.size:
                        r.font.size = Pt(44)
                    r.font.color.rgb = RGBColor(15, 98, 254)


def build_content_from_image(prs: Presentation, img: Image.Image) -> None:
    w, h = img.size
    buf = BytesIO()
    img.convert("RGB").save(buf, format="PNG")
    ocr_raw, _ = OCR(buf.getvalue())

    text_px = []
    if ocr_raw:
        for quad, text, score in ocr_raw:
            if score >= 0.5 and not is_footer(text):
                text_px.append(quad_to_rect(quad))

    texts = ocr_slide_image(img)

    diagrams = extract_diagrams(img, text_px)
    layout = choose_layout(len(texts), len(diagrams))
    slide = prs.slides.add_slide(get_layout(prs, layout))

    title = ""
    if texts:
        title_item = min(texts, key=lambda t: (t["top"], -t["font_size"]))
        if title_item["top"] < CONTENT_T + 0.9:
            title = title_item["text"]
            fill_title(slide, title)
            texts = [t for t in texts if t["text"] != title or abs(t["top"] - title_item["top"]) > 0.05]

    # Keep source lines in lower area; shift down if overlapping title placeholder zone
    for item in texts:
        if item["top"] < CONTENT_T + 0.75:
            item["top"] = CONTENT_T + 0.75

    place_diagrams(slide, diagrams, texts)
    for item in texts:
        add_text(slide, item)


def build() -> Path:
    shutil.copy2(TPL, OUT)
    prs = Presentation(str(OUT))
    src = Presentation(str(SRC_PPT))
    delete_all_slides(prs)

    build_cover(prs, src)
    for idx in range(1, len(src.slides)):
        sh = src.slides[idx].shapes[0]
        img = Image.open(BytesIO(sh.image.blob))
        build_content_from_image(prs, img)

    prs.slides.add_slide(get_layout(prs, "仅标题"))
    prs.save(str(OUT))
    return OUT


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    out = build()
    prs = Presentation(str(out))
    print(f"Generated: {out}")
    print(f"Slides: {len(prs.slides)}")
    for i, slide in enumerate(prs.slides, 1):
        nt = sum(1 for s in slide.shapes if s.has_text_frame and s.text_frame.text.strip())
        np = sum(1 for s in slide.shapes if s.shape_type == MSO_SHAPE_TYPE.PICTURE)
        print(f"  Slide {i:2d} [{slide.slide_layout.name}] text={nt} pictures={np}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
