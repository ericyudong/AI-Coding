from pptx import Presentation

src = r"c:\Users\E0008090\Desktop\ESmart\Cursor方案\2026-top-tech-trends-cn.pptx"
tpl = r"c:\Users\E0008090\Desktop\ESmart\Cursor方案\重庆PPT 模版1.pptx"

for label, path in [("SOURCE", src), ("TEMPLATE", tpl)]:
    prs = Presentation(path)
    print(f"=== {label} ===")
    print(f"Slides: {len(prs.slides)}")
    print(f"Slide size: {prs.slide_width.inches:.2f} x {prs.slide_height.inches:.2f} inches")
    print(f"Layouts: {len(prs.slide_layouts)}")
    for i, layout in enumerate(prs.slide_layouts):
        print(f"  Layout {i}: {layout.name}")
    for si, slide in enumerate(prs.slides):
        layout_name = slide.slide_layout.name if slide.slide_layout else "?"
        print(f"  Slide {si + 1}: layout={layout_name}, shapes={len(slide.shapes)}")
        for sh in slide.shapes:
            txt = ""
            if sh.has_text_frame:
                txt = sh.text_frame.text[:80].replace("\n", " ")
            print(f"    - type={sh.shape_type} name={sh.name!r} text={txt!r}")
    print()
