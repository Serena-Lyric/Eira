"""PDF parser using pypdf."""

from io import BytesIO
from . import ParsedDocument, EmptyTextError, register_parser


@register_parser(["application/pdf"])
class PdfParser:
    """Extract text from PDF documents using pypdf."""

    async def parse(self, content: bytes, filename: str) -> ParsedDocument:
        try:
            from pypdf import PdfReader
        except ImportError:
            raise ImportError(
                "pypdf is required for PDF parsing. Install with: pip install pypdf"
            )

        reader = PdfReader(BytesIO(content))
        pages: list[str] = []
        metadata: dict = {"filename": filename}

        # Extract document info if available
        if reader.metadata:
            info = reader.metadata
            if info.title:
                metadata["title"] = info.title
            if info.author:
                metadata["author"] = info.author

        for i, page in enumerate(reader.pages):
            text = page.extract_text()
            if text and text.strip():
                pages.append(text.strip())
            else:
                pages.append("")

        # Filter out empty pages
        non_empty = [p for p in pages if len(p) >= 20]

        if not non_empty:
            raise EmptyTextError(
                f"PDF '{filename}' produced no extractable text "
                f"(scanned images without OCR are not supported)"
            )

        full_text = "\n\n".join(non_empty)
        return ParsedDocument(
            text=full_text,
            page_count=len(reader.pages),
            metadata=metadata,
        )
