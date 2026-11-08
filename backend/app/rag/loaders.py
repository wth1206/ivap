"""Document loaders for PDF, DOCX and TXT.

PDF keeps real page numbers.  DOCX/TXT do not have stable physical pages, so
they return paragraph/line ranges instead of fabricating a page number.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import fitz  # PyMuPDF
from docx import Document

from app.core.exceptions import AppError
from app.rag.cleaner import clean_text

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TextBlock:
    text: str
    page_no: Optional[int] = None
    extra: Dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ParsedDocument:
    blocks: List[TextBlock]
    page_count: Optional[int]
    file_type: str

    @property
    def char_count(self) -> int:
        return sum(len(block.text) for block in self.blocks)


def _parse_pdf(path: Path) -> ParsedDocument:
    try:
        document = fitz.open(str(path))
    except Exception as exc:
        raise AppError("DOCUMENT_PARSE_FAILED", "PDF 无法打开", 400, {"reason": str(exc)[:200]}) from exc

    if document.needs_pass:
        document.close()
        raise AppError("DOCUMENT_ENCRYPTED", "PDF 已加密，暂不支持", 400)

    blocks: List[TextBlock] = []
    try:
        for index, page in enumerate(document):
            text = clean_text(page.get_text("text"))
            if text:
                blocks.append(
                    TextBlock(text=text, page_no=index + 1, extra={"page": index + 1})
                )
        page_count = document.page_count
    finally:
        document.close()

    parsed = ParsedDocument(blocks=blocks, page_count=page_count, file_type="pdf")
    if parsed.char_count < 50:
        raise AppError(
            "DOCUMENT_NO_TEXT",
            "PDF 中没有可提取的文本，可能是扫描件（暂不支持 OCR）",
            400,
        )
    return parsed


def _flush_paragraphs(
    blocks: List[TextBlock],
    buffer: List[str],
    start: int,
    end: int,
) -> None:
    if not buffer:
        return
    blocks.append(
        TextBlock(
            text=clean_text("\n".join(buffer)),
            page_no=None,
            extra={"paragraph_start": start + 1, "paragraph_end": end + 1},
        )
    )


def _parse_docx(path: Path) -> ParsedDocument:
    try:
        document = Document(str(path))
    except Exception as exc:
        raise AppError("DOCUMENT_PARSE_FAILED", "DOCX 无法打开", 400, {"reason": str(exc)[:200]}) from exc

    blocks: List[TextBlock] = []
    buffer: List[str] = []
    chars = 0
    start = 0

    for index, paragraph in enumerate(document.paragraphs):
        text = clean_text(paragraph.text)
        if not text:
            continue
        if not buffer:
            start = index
        buffer.append(text)
        chars += len(text)
        if chars >= 800:
            _flush_paragraphs(blocks, buffer, start, index)
            buffer = []
            chars = 0
    if buffer:
        _flush_paragraphs(blocks, buffer, start, len(document.paragraphs) - 1)

    for table_index, table in enumerate(document.tables):
        rows = []
        for row in table.rows:
            cells = [clean_text(cell.text) for cell in row.cells]
            cells = [cell for cell in cells if cell]
            if cells:
                rows.append(" | ".join(cells))
        if rows:
            blocks.append(
                TextBlock(
                    text=clean_text("\n".join(rows)),
                    page_no=None,
                    extra={"table_index": table_index},
                )
            )

    parsed = ParsedDocument(blocks=blocks, page_count=None, file_type="docx")
    if parsed.char_count < 20:
        raise AppError("DOCUMENT_NO_TEXT", "DOCX 中没有可提取的文本", 400)
    return parsed


def _read_txt(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "gb18030", "utf-16"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise AppError("DOCUMENT_PARSE_FAILED", "TXT 编码无法识别（支持 UTF-8/GB18030）", 400)


def _parse_txt(path: Path) -> ParsedDocument:
    text = clean_text(_read_txt(path))
    lines = text.split("\n") if text else []
    blocks: List[TextBlock] = []
    group_size = 30
    for start in range(0, len(lines), group_size):
        group = [line for line in lines[start : start + group_size] if line]
        if not group:
            continue
        blocks.append(
            TextBlock(
                text="\n".join(group),
                page_no=None,
                extra={
                    "line_start": start + 1,
                    "line_end": min(start + group_size, len(lines)),
                },
            )
        )
    parsed = ParsedDocument(blocks=blocks, page_count=None, file_type="txt")
    if parsed.char_count < 3:
        raise AppError("DOCUMENT_NO_TEXT", "TXT 文件为空", 400)
    return parsed


def parse_document(path: Path, file_type: str) -> ParsedDocument:
    file_type = file_type.lower()
    if file_type == "pdf":
        return _parse_pdf(path)
    if file_type == "docx":
        return _parse_docx(path)
    if file_type == "txt":
        return _parse_txt(path)
    raise AppError(
        "UNSUPPORTED_DOCUMENT_TYPE",
        "仅支持 PDF、DOCX、TXT",
        400,
        {"file_type": file_type},
    )
