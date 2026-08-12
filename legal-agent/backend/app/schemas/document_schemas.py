"""Document parsing schemas."""
from dataclasses import dataclass, field
from typing import Literal


@dataclass
class ParsedDocument:
    text: str
    source_type: Literal["pdf", "docx", "doc", "unknown"]
    page_count: int | None
    char_count: int
    warnings: list[str] = field(default_factory=list)
