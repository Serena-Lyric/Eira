"""Unified error response schema for all API endpoints (§16 fix).

All endpoints should use this format:
    { "error": "<machine-readable-code>", "message": "<human-readable 中文>", "cause": "<optional>" }
"""

from __future__ import annotations

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    """Standardized error response."""

    error: str            # Machine-readable error code (e.g. "file_too_large")
    message: str          # Human-readable Chinese description
    cause: str | None = None  # Optional technical detail for debugging

    @staticmethod
    def detail(code: str, message: str, cause: str | None = None) -> dict:
        """Convenience: return a dict suitable for HTTPException detail."""
        return ErrorResponse(error=code, message=message, cause=cause).model_dump()
