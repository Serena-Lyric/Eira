"""Audit middleware — logs all mutating admin requests for compliance.

Records POST/PUT/PATCH/DELETE operations under /admin/** paths.
Body is summarized (keys only, values truncated to 100 chars).
Sensitive fields (password, token, api_key, secret) are redacted.

Uses a fire-and-forget pattern to avoid blocking the response.
"""

from __future__ import annotations

import json
import structlog
from datetime import datetime, timezone

from starlette.types import ASGIApp, Receive, Scope, Send

logger = structlog.get_logger(__name__)

AUDIT_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
REDACT_FIELDS = frozenset({"password", "token", "api_key", "secret", "access_key", "refresh_token"})


def _summarize_body(body: bytes) -> dict:
    """Extract a safe summary of the request body for audit purposes.

    Returns a dict of field names → truncated values, with sensitive fields redacted.
    Non-JSON bodies return an empty dict.
    """
    if not body:
        return {}
    try:
        data = json.loads(body.decode("utf-8", errors="replace"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}

    if not isinstance(data, dict):
        return {"_raw_type": type(data).__name__}

    summary = {}
    for key, value in data.items():
        key_lower = key.lower()
        if any(s in key_lower for s in REDACT_FIELDS):
            summary[key] = "***"
        elif isinstance(value, str):
            summary[key] = value[:100] if len(value) > 100 else value
        elif isinstance(value, (int, float, bool)) or value is None:
            summary[key] = value
        else:
            summary[key] = f"<{type(value).__name__}>"
    return summary


class AuditMiddleware:
    """ASGI middleware that audits mutating admin requests."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        method = scope.get("method", "")

        # Only audit mutating admin requests
        if method not in AUDIT_METHODS or not path.startswith("/admin"):
            await self.app(scope, receive, send)
            return

        # Read request body
        body_chunks: list[bytes] = []

        async def receive_wrapper() -> dict:
            message = await receive()
            if message["type"] == "http.request":
                chunk = message.get("body", b"")
                if chunk:
                    body_chunks.append(chunk)
            return message

        # We need to consume the body and then re-create it for downstream
        # Since FastAPI/Starlette reads body once, we use a different approach:
        # store the body on the request state after constructing it

        await self.app(scope, receive_wrapper, send)

        # Fire-and-forget audit insertion (non-blocking)
        full_body = b"".join(body_chunks)
        body_summary = _summarize_body(full_body)

        # Extract user info if available (from auth header or request state)
        import asyncio
        asyncio.ensure_future(self._record(
            path=path,
            method=method,
            body_summary=body_summary,
            client_ip=self._get_client_ip(scope),
        ))

    async def _record(self, path: str, method: str, body_summary: dict, client_ip: str | None) -> None:
        """Persist audit log entry to the database."""
        try:
            from app.infra.db import get_session_factory
            from sqlalchemy import text

            factory = get_session_factory()
            async with factory() as session:
                await session.execute(
                    text(
                        """INSERT INTO audit_log (action, path, method, body_summary, ip_address)
                           VALUES (:action, :path, :method, :body_summary, :ip_address)"""
                    ),
                    {
                        "action": f"{method}:{path.split('/')[2] if len(path.split('/')) > 2 else 'admin'}",
                        "path": path,
                        "method": method,
                        "body_summary": json.dumps(body_summary),
                        "ip_address": client_ip,
                    },
                )
                await session.commit()
        except Exception as exc:
            # Audit failure must never affect the response
            logger.warning("audit.write_failed", path=path, method=method, error=str(exc))

    @staticmethod
    def _get_client_ip(scope: Scope) -> str | None:
        """Extract client IP from ASGI scope headers."""
        for key, value in scope.get("headers", []):
            if key == b"x-forwarded-for":
                return value.decode("utf-8", errors="replace").split(",")[0].strip()
        for key, value in scope.get("headers", []):
            if key == b"x-real-ip":
                return value.decode("utf-8", errors="replace")
        client = scope.get("client")
        if client:
            return client[0]
        return None
