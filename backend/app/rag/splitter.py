"""Character-based chunking with page/paragraph metadata preserved."""

from dataclasses import dataclass
from typing import Dict, List, Optional

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.rag.loaders import ParsedDocument

_SEPARATORS = ["\n\n", "\n", "。", "；", "！", "？", "，", " ", ""]


@dataclass(frozen=True)
class Chunk:
    chunk_index: int
    content: str
    page_no: Optional[int]
    char_start: int
    char_end: int
    extra: Dict[str, object]


def split_document(
    parsed: ParsedDocument,
    chunk_size: int = 500,
    chunk_overlap: int = 80,
) -> List[Chunk]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=_SEPARATORS,
        keep_separator=True,
        strip_whitespace=True,
    )

    chunks: List[Chunk] = []
    index = 0
    for block in parsed.blocks:
        pieces = splitter.split_text(block.text)
        cursor = 0
        for piece in pieces:
            content = piece.strip()
            if len(content) < 5:
                continue
            start = block.text.find(content, cursor)
            if start < 0:
                start = cursor
            end = start + len(content)
            cursor = max(end, start + 1)

            extra = dict(block.extra or {})
            extra["char_start"] = start
            extra["char_end"] = end
            chunks.append(
                Chunk(
                    chunk_index=index,
                    content=content,
                    page_no=block.page_no,
                    char_start=start,
                    char_end=end,
                    extra=extra,
                )
            )
            index += 1

    return chunks
