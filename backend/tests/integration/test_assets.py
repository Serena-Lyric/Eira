"""Integration tests for Assets REST API (T3.7)."""

import uuid

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _register_and_login(c: AsyncClient) -> tuple[str, int]:
    email = f"asset-{uuid.uuid4().hex[:8]}@example.com"
    r = await c.post(
        "/auth/register",
        json={"email": email, "password": "Passw0rd!", "display_name": "AT"},
    )
    assert r.status_code == 201, r.text
    uid = r.json()["id"]
    r = await c.post("/auth/login", json={"email": email, "password": "Passw0rd!"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"], uid


# ── Backgrounds ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_upload_background_requires_auth():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post("/assets/backgrounds")
        assert r.status_code == 401


@pytest.mark.asyncio
async def test_upload_background_jpeg():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        token, _ = await _register_and_login(c)

        # Small JPEG bytes (valid JFIF header + minimal data)
        jpeg = (
            b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
            b"\xff\xdb\x00C\x00\x03\x02\x02\x02\x02\x02\x03\x02\x02\x02\x03\x03\x03"
            b"\x03\x04\x06\x04\x04\x04\x04\x04\x08\x06\x06\x05\x06\t\n\n\t\t\t\t\t"
            b"\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f"
            b"\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00"
            b"\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xc4\x00\xb5\x10\x00"
            b"\x02\x01\x03\x03\x02\x04\x03\x05\x05\x04\x04\x00\x00\x01}\x01\x02\x03"
            b"\x00\x04\x11\x05\x12!1A\x06\x13Qa\x07\"q\x142\x81\x91\xa1\xff\xda"
            b"\x00\x08\x01\x01\x00\x00?\x00\x1f\x00\x00\x00\x00\x00\x00\xff\xd9"
        )

        r = await c.post(
            "/assets/backgrounds",
            files={"file": ("bg.jpg", jpeg, "image/jpeg")},
            headers=_bearer(token),
        )
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["success"] is True
        assert data["asset_id"] > 0


@pytest.mark.asyncio
async def test_upload_background_rejects_wrong_type():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        token, _ = await _register_and_login(c)
        r = await c.post(
            "/assets/backgrounds",
            files={"file": ("test.txt", b"not an image", "text/plain")},
            headers=_bearer(token),
        )
        assert r.status_code == 400


@pytest.mark.asyncio
async def test_list_backgrounds():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        token, _ = await _register_and_login(c)
        r = await c.get("/assets/backgrounds", headers=_bearer(token))
        assert r.status_code == 200
        data = r.json()
        assert "items" in data
        assert "total" in data


@pytest.mark.asyncio
async def test_delete_background_not_found():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        token, _ = await _register_and_login(c)
        r = await c.delete("/assets/backgrounds/99999", headers=_bearer(token))
        assert r.status_code == 404


# ── Live2D models ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_upload_live2d_requires_auth():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post("/assets/live2d")
        assert r.status_code == 401


@pytest.mark.asyncio
async def test_upload_live2d_rejects_non_zip():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        token, _ = await _register_and_login(c)
        r = await c.post(
            "/assets/live2d",
            files={"file": ("model.txt", b"not a zip", "text/plain")},
            headers=_bearer(token),
        )
        assert r.status_code == 400


@pytest.mark.asyncio
async def test_upload_live2d_rejects_invalid_zip():
    """Upload a zip without model3.json should fail."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        token, _ = await _register_and_login(c)

        # Create a minimal zip without model3.json
        import io, zipfile
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("readme.txt", "not a model")
        invalid_zip = buf.getvalue()

        r = await c.post(
            "/assets/live2d",
            files={"file": ("model.zip", invalid_zip, "application/zip")},
            headers=_bearer(token),
        )
        assert r.status_code == 400, r.text
        assert "model3.json" in r.json()["detail"]


# ── Quota ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_quota():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        token, _ = await _register_and_login(c)
        r = await c.get("/assets/quota/background", headers=_bearer(token))
        assert r.status_code == 200
        data = r.json()
        assert data["kind"] == "background"
        assert "used" in data
        assert "limit" in data
        assert data["limit"] == 5  # Default background quota


@pytest.mark.asyncio
async def test_quota_invalid_kind():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        token, _ = await _register_and_login(c)
        r = await c.get("/assets/quota/invalid", headers=_bearer(token))
        assert r.status_code == 400


# ── URL signing ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_background_url_not_found():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        token, _ = await _register_and_login(c)
        r = await c.get("/assets/backgrounds/99999/url", headers=_bearer(token))
        assert r.status_code == 404


@pytest.mark.asyncio
async def test_list_live2d_models():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        token, _ = await _register_and_login(c)
        r = await c.get("/assets/live2d", headers=_bearer(token))
        assert r.status_code == 200
        data = r.json()
        assert "items" in data
