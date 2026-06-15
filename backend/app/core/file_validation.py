"""Magic number (file header) validation for upload endpoints.

Validates that uploaded file content matches its declared MIME type by checking
the leading bytes, preventing trivial MIME spoofing (e.g. a .txt renamed to .jpg).

Reference: spec §7.5 — magic number verification required for all upload endpoints.
"""

from __future__ import annotations


def normalize_mime(mime: str) -> str:
    """Normalize a MIME type string for reliable comparison.

    - Lowercase
    - Strip whitespace
    - Remove parameters (e.g. ``text/plain; charset=utf-8`` → ``text/plain``)
    - Normalize common aliases (e.g. ``image/jpg`` → ``image/jpeg``)
    """
    if not mime:
        return ""
    mime = mime.strip().lower()
    mime = mime.split(";")[0].strip()
    # Common aliases
    _ALIASES = {"image/jpg": "image/jpeg"}
    return _ALIASES.get(mime, mime)


# Mapping of MIME type → list of acceptable leading byte sequences.
# For some formats there are multiple valid signatures (e.g. empty ZIP).
MAGIC_BYTES: dict[str, list[bytes]] = {
    "image/jpeg": [b"\xff\xd8\xff"],
    "image/png": [b"\x89PNG\r\n\x1a\n"],
    # WebP: RIFF container with WEBP fourcc at offset 8
    "image/webp": [b"RIFF"],
    "application/pdf": [b"%PDF"],
    "application/zip": [b"PK\x03\x04", b"PK\x05\x06"],
    # Office Open XML (.docx / .xlsx / .pptx) are ZIP archives
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [
        b"PK\x03\x04",
        b"PK\x05\x06",
    ],
}

# Text-based formats — scan for binary indicators to reject files
# that claim to be text but are actually binary.
_TEXT_MIMES = {"text/plain", "text/markdown", "text/csv"}


def _looks_like_binary(content: bytes, sample_size: int = 512) -> bool:
    """Return True if *content* looks like binary data.

    Heuristic: scan the first *sample_size* bytes.  If the null-byte ratio
    exceeds 10 %, treat the content as binary.  This catches most executables,
    compressed archives, and media files disguised as text.
    """
    sample = content[:sample_size]
    if not sample:
        return False
    null_ratio = sample.count(b"\x00") / len(sample)
    return null_ratio > 0.10


def validate_magic(content: bytes, expected_mime: str) -> bool:
    """Return True if *content* starts with a valid header for *expected_mime*.

    For text types we scan the leading bytes for binary indicators (null-byte
    ratio).  For binary image/document types we check against the hard-coded
    signature table above.
    """
    if not content:
        return False

    if expected_mime in _TEXT_MIMES:
        # Text files: reject if content looks binary
        return not _looks_like_binary(content)

    signatures = MAGIC_BYTES.get(expected_mime)
    if not signatures:
        # Unknown MIME — allow through (future-proof)
        return True

    # WebP: must have RIFF header AND WEBP fourcc at offset 8
    if expected_mime == "image/webp":
        if not content.startswith(b"RIFF") or len(content) < 12:
            return False
        return content[8:12] == b"WEBP"

    return any(content.startswith(sig) for sig in signatures)
