# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding="utf-8")

import fitz
from pptx import Presentation

pdf_path = r"c:\Users\E0008090\Desktop\ESmart\Cursor方案\2026-top-tech-trends-cn.pdf"
ppt_path = r"c:\Users\E0008090\Desktop\ESmart\Cursor方案\2026-top-tech-trends-cn.pptx"

doc = fitz.open(pdf_path)
print(f"PDF pages: {doc.page_count}")

for i in range(doc.page_count):
    page = doc[i]
    blocks = page.get_text("dict")["blocks"]
    text_blocks = []
    image_blocks = []
    for b in blocks:
        if b["type"] == 0:  # text
            lines = []
            for line in b["lines"]:
                spans = []
                for span in line["spans"]:
                    spans.append({
                        "text": span["text"],
                        "size": round(span["size"], 1),
                        "font": span["font"],
                        "color": span["color"],
                        "bbox": [round(x, 1) for x in span["bbox"]],
                    })
                lines.append(spans)
            text_blocks.append({"bbox": [round(x, 1) for x in b["bbox"]], "lines": lines})
        elif b["type"] == 1:  # image
            image_blocks.append({"bbox": [round(x, 1) for x in b["bbox"]]})

    print(f"\n=== PDF Page {i+1} ({page.rect.width:.0f}x{page.rect.height:.0f}) ===")
    print(f"  text blocks: {len(text_blocks)}, image blocks: {len(image_blocks)}")
    for j, tb in enumerate(text_blocks[:8]):
        sample = ""
        for line in tb["lines"][:2]:
            for sp in line[:1]:
                sample += sp["text"]
        print(f"  T{j+1} bbox={tb['bbox']} sample={sample[:60]!r}")
    if len(text_blocks) > 8:
        print(f"  ... +{len(text_blocks)-8} more text blocks")

# PPT slide count
prs = Presentation(ppt_path)
print(f"\nPPT slides: {len(prs.slides)}")
