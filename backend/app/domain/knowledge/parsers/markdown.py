"""Markdown parser (extracts plain text)."""

import re
from . import ParsedDocument, EmptyTextError, register_parser


# Note: markdown-it-py is optional; fallback to regex-based stripping
@register_parser(["text/markdown"])
class MarkdownParser:
    """Extract plain text from Markdown documents."""

    async def parse(self, content: bytes, filename: str) -> ParsedDocument:
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            for enc in ("gbk", "gb2312", "latin-1"):
                try:
                    text = content.decode(enc)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                raise EmptyTextError(
                    f"Unable to decode markdown file '{filename}'"
                )

        # Try markdown-it-py for better parsing
        plain = _strip_markdown(text)

        lines = plain.split("\n")
        meaningful = [line.strip() for line in lines if len(line.strip()) >= 20]

        if not meaningful:
            raise EmptyTextError(
                f"Markdown file '{filename}' contains no meaningful content"
            )

        return ParsedDocument(
            text="\n\n".join(meaningful),
            page_count=1,
            metadata={"filename": filename},
        )


def _strip_markdown(text: str) -> str:
    """Strip markdown formatting to extract plain text.

    Tries markdown-it-py first, falls back to regex.
    """
    try:
        from markdown_it import MarkdownIt
        md = MarkdownIt()
        # Render to HTML then strip tags
        html = md.render(text)
        plain = _strip_html(html)
        if plain.strip():
            return plain
    except ImportError:
        pass

    # Fallback: regex-based stripping
    # Remove code blocks
    text = re.sub(r"```[\s\S]*?```", " ", text)
    # Remove inline code
    text = re.sub(r"`[^`]+`", " ", text)
    # Remove images
    text = re.sub(r"!\[.*?\]\(.*?\)", " ", text)
    # Remove links but keep text
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    # Remove headers
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    # Remove bold/italic
    text = re.sub(r"\*{1,3}([^*]+)\*{1,3}", r"\1", text)
    # Remove horizontal rules
    text = re.sub(r"^[-*_]{3,}\s*$", "", text, flags=re.MULTILINE)
    # Remove blockquote markers
    text = re.sub(r"^>\s+", "", text, flags=re.MULTILINE)
    # Remove list markers
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\d+\.\s+", "", text, flags=re.MULTILINE)
    # Remove HTML tags
    text = _strip_html(text)
    return text


def _strip_html(html: str) -> str:
    """Remove HTML tags."""
    return re.sub(r"<[^>]+>", " ", html)
