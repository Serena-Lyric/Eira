"""Integration tests for documents REST API."""

import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _register_and_login(c: AsyncClient) -> tuple[str, int]:
    email = f"doc-{uuid.uuid4().hex[:8]}@example.com"
    r = await c.post(
        "/auth/register",
        json={"email": email, "password": "Passw0rd!", "display_name": "T"},
    )
    assert r.status_code == 201
    uid = r.json()["id"]
    r = await c.post(
        "/auth/login",
        json={"email": email, "password": "Passw0rd!"},
    )
    assert r.status_code == 200
    return r.json()["access_token"], uid


@pytest.mark.asyncio
async def test_upload_requires_auth():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post("/documents/upload")
        assert r.status_code == 401


@pytest.mark.asyncio
async def test_upload_rejects_unsupported_type():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        token, _ = await _register_and_login(c)
        r = await c.post(
            "/documents/upload",
            files={"file": ("test.exe", b"fake", "application/octet-stream")},
            headers=_bearer(token),
        )
        assert r.status_code == 400
        assert "不支持" in r.json()["detail"] or "文件类型" in r.json()["detail"]


@pytest.mark.asyncio
async def test_upload_text_file():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        token, _ = await _register_and_login(c)
        content = (
            "这是一个测试文档，内容足够长来满足最小段落过滤要求。"
            "景区介绍：西湖位于中国浙江省杭州市，是著名的旅游景点。"
        ).encode("utf-8")
        r = await c.post(
            "/documents/upload",
            files={"file": ("guide.txt", content, "text/plain")},
            headers=_bearer(token),
        )
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["document_id"] > 0
        assert data["filename"] == "guide.txt"
        assert data["status"] == "pending"


@pytest.mark.asyncio
async def test_list_documents():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        token, _ = await _register_and_login(c)
        r = await c.get("/documents", headers=_bearer(token))
        assert r.status_code == 200
        data = r.json()
        assert "items" in data
        assert "total" in data


@pytest.mark.asyncio
async def test_get_document_not_found():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        token, _ = await _register_and_login(c)
        r = await c.get("/documents/99999", headers=_bearer(token))
        assert r.status_code == 404


@pytest.mark.asyncio
async def test_delete_requires_admin():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        token, _ = await _register_and_login(c)
        r = await c.delete("/documents/1", headers=_bearer(token))
        # Regular user cannot delete — 403 forbidden
        assert r.status_code in (403, 404)


@pytest.mark.asyncio
async def test_reprocess_requires_admin():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        token, _ = await _register_and_login(c)
        r = await c.post("/documents/1/reprocess", headers=_bearer(token))
        assert r.status_code in (403, 404)
