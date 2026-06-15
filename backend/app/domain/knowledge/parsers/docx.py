"""DOCX parser using python-docx."""

from io import BytesIO
from . import ParsedDocument, EmptyTextError, register_parser


@register_parser([
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
])
class DocxParser:
    """Extract text from DOCX documents using python-docx."""

    async def parse(self, content: bytes, filename: str) -> ParsedDocument:
        try:
            from docx import Document as DocxDocument
        except ImportError:
            raise ImportError(
                "python-docx is required for DOCX parsing. "
                "Install with: pip install python-docx"
            )

        doc = DocxDocument(BytesIO(content))
        paragraphs: list[str] = []

        # Extract paragraphs
        for para in doc.paragraphs:
            text = para.text.strip()
            if len(text) >= 20:
                paragraphs.append(text)

        # Extract table text (concatenate rows)
        for table in doc.tables:
            for row in table.rows:
                cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                if cells:
                    row_text = " | ".join(cells)
                    if len(row_text) >= 20:
                        paragraphs.append(row_text)

        if not paragraphs:
            raise EmptyTextError(
                f"DOCX '{filename}' produced no extractable text"
            )

        full_text = "\n\n".join(paragraphs)
        return ParsedDocument(
            text=full_text,
            page_count=len(paragraphs),  # rough estimate
            metadata={"filename": filename},
        )
