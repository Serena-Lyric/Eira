"""Plain text parser."""

from . import ParsedDocument, EmptyTextError, register_parser


@register_parser(["text/plain", "text/markdown"])
class TextParser:
    """Extract text from plain text documents."""

    async def parse(self, content: bytes, filename: str) -> ParsedDocument:
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            # Try common fallback encodings
            for enc in ("gbk", "gb2312", "latin-1"):
                try:
                    text = content.decode(enc)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                raise EmptyTextError(
                    f"Unable to decode text file '{filename}' (tried utf-8, gbk, gb2312, latin-1)"
                )

        # Filter paragraphs: minimum 20 characters
        lines = text.split("\n")
        meaningful = [line.strip() for line in lines if len(line.strip()) >= 20]

        if not meaningful:
            raise EmptyTextError(
                f"Text file '{filename}' contains no meaningful content"
            )

        return ParsedDocument(
            text="\n\n".join(meaningful),
            page_count=1,
            metadata={"filename": filename},
        )
