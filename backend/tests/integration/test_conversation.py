"""Integration tests for conversation domain + REST endpoints (T1.3)."""

import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _register_and_login(c: AsyncClient) -> tuple[str, int]:
    """Register a user, log in, and return (access_token, user_id)."""
    email = f"conv-{uuid.uuid4().hex[:8]}@example.com"
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
async def test_create_and_list_sessions():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        token, _uid = await _register_and_login(c)

        # Create two sessions
        r1 = await c.post(
            "/conversations",
            json={"title": "Chat 1"},
            headers=_bearer(token),
        )
        assert r1.status_code == 201, r1.text
        s1 = r1.json()
        assert s1["title"] == "Chat 1"

        r2 = await c.post(
            "/conversations",
            json={"title": "Chat 2"},
            headers=_bearer(token),
        )
        assert r2.status_code == 201
        s2 = r2.json()

        # List — newest first
        r = await c.get("/conversations", headers=_bearer(token))
        assert r.status_code == 200
        data = r.json()
        assert data["total"] >= 2
        ids = [s["id"] for s in data["sessions"]]
        # newest first
        assert ids.index(s2["id"]) < ids.index(s1["id"])


@pytest.mark.asyncio
async def test_get_messages_empty():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        token, _uid = await _register_and_login(c)
        r = await c.post(
            "/conversations",
            json={"title": "Empty"},
            headers=_bearer(token),
        )
        sid = r.json()["id"]

        r = await c.get(
            f"/conversations/{sid}/messages",
            headers=_bearer(token),
        )
        assert r.status_code == 200
        assert r.json() == []


@pytest.mark.asyncio
async def test_cannot_access_other_users_session():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        token1, _ = await _register_and_login(c)

        r = await c.post(
            "/conversations",
            json={"title": "Private"},
            headers=_bearer(token1),
        )
        sid = r.json()["id"]

        # Another user
        token2, _ = await _register_and_login(c)
        r = await c.get(
            f"/conversations/{sid}/messages",
            headers=_bearer(token2),
        )
        assert r.status_code == 404


@pytest.mark.asyncio
async def test_create_session_requires_auth():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post("/conversations", json={"title": "X"})
        assert r.status_code == 401
