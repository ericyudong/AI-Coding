"""Contract text chunking for review, indexing and RAG."""
import re
from dataclasses import dataclass


@dataclass
class TextChunk:
    content: str
    section_title: str
    start_offset: int
    index: int


_CLAUSE_PATTERN = re.compile(
    r"(?:^|\n)\s*(第[一二三四五六七八九十百零\d]+条[^\n]*)",
    re.MULTILINE,
)


def chunk_contract_text(
    text: str,
    chunk_size: int = 800,
    overlap: int = 100,
) -> list[TextChunk]:
    """Split contract text by clause headings, fallback to sliding window."""
    text = text.strip()
    if not text:
        return []

    matches = list(_CLAUSE_PATTERN.finditer(text))
    if len(matches) >= 2:
        chunks: list[TextChunk] = []
        for i, m in enumerate(matches):
            start = m.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            section = m.group(1).strip()
            content = text[start:end].strip()
            if content:
                chunks.append(
                    TextChunk(
                        content=content,
                        section_title=section,
                        start_offset=start,
                        index=len(chunks),
                    )
                )
        if chunks:
            return chunks

    # Paragraph-based fallback
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if not paragraphs:
        paragraphs = [text]

    chunks = []
    buf = ""
    offset = 0
    for para in paragraphs:
        if len(buf) + len(para) + 2 <= chunk_size:
            buf = f"{buf}\n\n{para}".strip() if buf else para
        else:
            if buf:
                chunks.append(
                    TextChunk(
                        content=buf,
                        section_title=f"片段 {len(chunks) + 1}",
                        start_offset=offset,
                        index=len(chunks),
                    )
                )
                offset += max(len(buf) - overlap, 0)
            if len(para) <= chunk_size:
                buf = para
            else:
                for j in range(0, len(para), chunk_size - overlap):
                    piece = para[j : j + chunk_size]
                    chunks.append(
                        TextChunk(
                            content=piece,
                            section_title=f"片段 {len(chunks) + 1}",
                            start_offset=offset + j,
                            index=len(chunks),
                        )
                    )
                buf = ""
    if buf:
        chunks.append(
            TextChunk(
                content=buf,
                section_title=f"片段 {len(chunks) + 1}",
                start_offset=offset,
                index=len(chunks),
            )
        )
    return chunks
