"""Document parser registry — maps MIME types to parser implementations."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class ParsedDocument:
    """Result of parsing a document."""
    text: str
    page_count: int = 1
    metadata: dict = field(default_factory=dict)


class EmptyTextError(Exception):
    """Raised when a document yields no extractable text."""


class BaseParser(Protocol):
    """Protocol for document parsers."""

    async def parse(self, content: bytes, filename: str) -> ParsedDocument: ...


# MIME type → parser mapping (populated by each parser module)
_registry: dict[str, type] = {}


def register_parser(mime_types: list[str]):
    """Decorator to register a parser class for one or more MIME types."""
    def decorator(cls: type):
        for mt in mime_types:
            _registry[mt] = cls
        return cls
    return decorator


def get_parser(mime_type: str) -> type | None:
    """Look up a parser class by MIME type."""
    return _registry.get(mime_type)


def supported_mime_types() -> list[str]:
    """Return all supported MIME types."""
    return list(_registry.keys())


# Import parser modules to trigger @register_parser decorations
from . import text    # noqa: F401, E402
from . import pdf     # noqa: F401, E402
from . import docx    # noqa: F401, E402
from . import markdown  # noqa: F401, E402
