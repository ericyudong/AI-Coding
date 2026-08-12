"""Local OCR for scanned PDF pages (RapidOCR + PyMuPDF)."""
from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

_ocr_engine = None
_ocr_unavailable_reason: str | None = None


@lru_cache(maxsize=1)
def _check_ocr_available() -> tuple[bool, str | None]:
    try:
        from rapidocr_onnxruntime import RapidOCR  # noqa: F401
        import fitz  # noqa: F401
    except ImportError as exc:
        return False, f"OCR 依赖未安装（rapidocr-onnxruntime、pymupdf）：{exc}"
    return True, None


def get_ocr_engine():
    global _ocr_engine, _ocr_unavailable_reason
    ok, reason = _check_ocr_available()
    if not ok:
        _ocr_unavailable_reason = reason
        return None
    if _ocr_engine is None:
        from rapidocr_onnxruntime import RapidOCR

        _ocr_engine = RapidOCR()
    return _ocr_engine


def ocr_unavailable_reason() -> str | None:
    get_ocr_engine()
    return _ocr_unavailable_reason


def render_pdf_pages(path: Path, max_pages: int, dpi: int) -> list[tuple[int, bytes]]:
    import fitz

    doc = fitz.open(str(path))
    pages: list[tuple[int, bytes]] = []
    try:
        for index, page in enumerate(doc):
            if index >= max_pages:
                break
            matrix = fitz.Matrix(dpi / 72, dpi / 72)
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            pages.append((index + 1, pix.tobytes("png")))
    finally:
        doc.close()
    return pages


def ocr_image_bytes(image_bytes: bytes, *, min_score: float = 0.5) -> str:
    engine = get_ocr_engine()
    if engine is None:
        return ""

    result, _ = engine(image_bytes)
    if not result:
        return ""

    items: list[tuple[float, float, str]] = []
    for quad, text, score in result:
        if score < min_score:
            continue
        line = (text or "").strip()
        if not line:
            continue
        ys = [p[1] for p in quad]
        xs = [p[0] for p in quad]
        items.append((min(ys), min(xs), line))

    items.sort(key=lambda item: (round(item[0], 1), item[1]))
    return "\n".join(line for _, _, line in items)


def ocr_pdf_pages(
    path: Path,
    *,
    page_numbers: list[int],
    max_pages: int,
    dpi: int,
    min_score: float = 0.5,
) -> dict[int, str]:
    """OCR selected 1-based page numbers. Returns {page_no: text}."""
    if not page_numbers:
        return {}

    rendered = {num: data for num, data in render_pdf_pages(path, max_pages, dpi)}
    out: dict[int, str] = {}
    for page_no in page_numbers:
        png = rendered.get(page_no)
        if not png:
            continue
        text = ocr_image_bytes(png, min_score=min_score)
        if text.strip():
            out[page_no] = text.strip()
            logger.info("OCR page %s: %s chars from %s", page_no, len(text), path.name)
    return out
