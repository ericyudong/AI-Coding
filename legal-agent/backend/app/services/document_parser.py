"""Unified document parser for PDF and DOCX."""
from pathlib import Path

from app.core.config import get_settings
from app.schemas.document_schemas import ParsedDocument


def _parse_pdf(file_path: Path, max_pages: int) -> ParsedDocument:
    from pypdf import PdfReader

    settings = get_settings()
    warnings: list[str] = []
    reader = PdfReader(str(file_path))
    page_count = len(reader.pages)
    if page_count > max_pages:
        warnings.append(f"文档共 {page_count} 页，仅解析前 {max_pages} 页")

    page_texts: list[str] = []
    empty_pages = 0
    for page in reader.pages[:max_pages]:
        text = (page.extract_text() or "").strip()
        page_texts.append(text)
        if not text:
            empty_pages += 1

    ocr_pages: list[int] = []
    if settings.parser_ocr_enabled:
        for i, text in enumerate(page_texts, start=1):
            if len(text) < settings.parser_ocr_min_page_chars:
                ocr_pages.append(i)
    elif empty_pages == page_count:
        warnings.append("PDF 未提取到文本，可能为扫描件；可在 .env 中设置 PARSER_OCR_ENABLED=true 启用本地 OCR")

    if settings.parser_ocr_enabled and ocr_pages:
        from app.services import document_ocr

        if document_ocr.ocr_unavailable_reason():
            warnings.append(document_ocr.ocr_unavailable_reason() or "本地 OCR 不可用")
        else:
            try:
                ocr_results = document_ocr.ocr_pdf_pages(
                    file_path,
                    page_numbers=ocr_pages,
                    max_pages=max_pages,
                    dpi=settings.parser_ocr_dpi,
                    min_score=settings.parser_ocr_min_score,
                )
                ocr_hit = 0
                for page_no, ocr_text in ocr_results.items():
                    idx = page_no - 1
                    if 0 <= idx < len(page_texts):
                        if page_texts[idx]:
                            page_texts[idx] = f"{page_texts[idx]}\n{ocr_text}"
                        else:
                            page_texts[idx] = ocr_text
                        ocr_hit += 1
                if ocr_hit:
                    warnings.append(f"已对 {ocr_hit} 页扫描内容使用本地 OCR（RapidOCR）识别")
                    empty_pages = sum(1 for t in page_texts if not t.strip())
                elif ocr_pages:
                    warnings.append("已尝试本地 OCR，但未识别到有效文字，请检查扫描清晰度")
            except Exception as exc:
                logger_msg = f"本地 OCR 处理失败: {exc}"
                warnings.append(logger_msg)

    if empty_pages == page_count and not any(page_texts):
        if not any("OCR" in w or "ocr" in w.lower() for w in warnings):
            warnings.append("PDF 未提取到文本，可能为扫描件，需启用本地 OCR 或换用 Word 版")
    elif empty_pages > 0:
        warnings.append(f"有 {empty_pages} 页未提取到文本")

    text = "\n\n".join(t for t in page_texts if t.strip())
    return ParsedDocument(
        text=text,
        source_type="pdf",
        page_count=page_count,
        char_count=len(text),
        warnings=warnings,
    )


def _parse_docx(file_path: Path) -> ParsedDocument:
    from docx import Document

    doc = Document(str(file_path))
    parts: list[str] = []
    for para in doc.paragraphs:
        t = para.text.strip()
        if t:
            parts.append(t)
    for table in doc.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells if c.text.strip()]
            if cells:
                parts.append(" | ".join(cells))

    text = "\n".join(parts)
    warnings: list[str] = []
    if not text:
        warnings.append("DOCX 未提取到文本内容")
    return ParsedDocument(
        text=text,
        source_type="docx",
        page_count=None,
        char_count=len(text),
        warnings=warnings,
    )


def parse_file(file_path: str | Path) -> ParsedDocument:
    """Parse PDF/DOCX to plain text."""
    path = Path(file_path)
    if not path.exists():
        return ParsedDocument(
            text="",
            source_type="unknown",
            page_count=None,
            char_count=0,
            warnings=[f"文件不存在: {path}"],
        )

    settings = get_settings()
    ext = path.suffix.lower()
    if ext == ".pdf":
        return _parse_pdf(path, settings.parser_max_pages)
    if ext == ".docx":
        return _parse_docx(path)
    if ext == ".doc":
        return ParsedDocument(
            text="",
            source_type="doc",
            page_count=None,
            char_count=0,
            warnings=["旧版 .doc 格式暂不支持，请转换为 .docx 后上传"],
        )
    return ParsedDocument(
        text="",
        source_type="unknown",
        page_count=None,
        char_count=0,
        warnings=[f"不支持的文件格式: {ext}"],
    )
