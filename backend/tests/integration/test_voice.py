"""Integration tests for voice REST endpoints — TTS + ASR (P0-3 fix)."""

import uuid

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _register_and_login(c: AsyncClient) -> str:
    email = f"voice-{uuid.uuid4().hex[:8]}@example.com"
    r = await c.post(
        "/auth/register",
        json={"email": email, "password": "Passw0rd!", "display_name": "VT"},
    )
    assert r.status_code == 201, r.text
    r = await c.post("/auth/login", json={"email": email, "password": "Passw0rd!"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


# ── ASR endpoint registration ──────────────────────────────────────────


def test_asr_endpoint_registered():
    """P0-3: POST /voice/asr route is registered."""
    post_routes = [
        r for r in app.routes
        if hasattr(r, "path") and r.path == "/voice/asr" and "POST" in r.methods
    ]
    assert len(post_routes) == 1, "POST /voice/asr route should be registered"


# ── ASR auth ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_asr_requires_auth():
    """P0-3: POST /voice/asr without token returns 401."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post("/voice/asr")
        assert r.status_code == 401, r.text


# ── ASR recognition ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_asr_returns_text():
    """P0-3: POST audio returns {text: string} (mock provider)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        token = await _register_and_login(c)

        # Send synthetic audio bytes (mock provider doesn't actually analyze them)
        audio_content = b"\x00" * 4096  # 4KB of silence
        r = await c.post(
            "/voice/asr",
            files={"audio": ("test.webm", audio_content, "audio/webm")},
            headers=_bearer(token),
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert "text" in data
        assert isinstance(data["text"], str)
        assert len(data["text"]) > 0
        # Mock provider returns Chinese text by default
        assert any('一' <= c <= '鿿' for c in data["text"]), \
            f"Expected Chinese text, got: {data['text']}"


@pytest.mark.asyncio
async def test_asr_empty_audio_rejected():
    """P0-3: Empty audio file returns 400."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        token = await _register_and_login(c)

        r = await c.post(
            "/voice/asr",
            files={"audio": ("empty.webm", b"", "audio/webm")},
            headers=_bearer(token),
        )
        assert r.status_code == 400, r.text
        assert "音频文件为空" in r.json()["detail"]


# ── TTS (existing functionality — regression check) ────────────────────


@pytest.mark.asyncio
async def test_tts_endpoint_exists():
    """POST /voice/tts returns audio response."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        token = await _register_and_login(c)

        r = await c.post(
            "/voice/tts",
            json={"text": "你好世界"},
            headers=_bearer(token),
        )
        assert r.status_code == 200, r.text
        assert r.headers["content-type"] == "audio/opus"


# ── ASR config ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_asr_config_returns_structure():
    """GET /voice/asr/config returns expected schema."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        token = await _register_and_login(c)

        r = await c.get("/voice/asr/config", headers=_bearer(token))
        assert r.status_code == 200, r.text
        data = r.json()
        assert "provider" in data
        assert "enabled" in data
        assert isinstance(data["enabled"], bool)
