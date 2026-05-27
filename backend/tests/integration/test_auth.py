import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_register_login_refresh_flow():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post(
            "/auth/register",
            json={
                "email": "u1@example.com",
                "password": "Passw0rd!",
                "display_name": "U1",
            },
        )
        assert r.status_code == 201, r.text

        r = await c.post(
            "/auth/login",
            json={"email": "u1@example.com", "password": "Passw0rd!"},
        )
        assert r.status_code == 200
        tokens = r.json()
        assert "access_token" in tokens and "refresh_token" in tokens

        r = await c.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        assert r.status_code == 200
        assert r.json()["email"] == "u1@example.com"

        r = await c.post(
            "/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
        )
        assert r.status_code == 200
        assert r.json()["access_token"] != tokens["access_token"]


@pytest.mark.asyncio
async def test_login_fail_does_not_leak_user_existence():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r1 = await c.post(
            "/auth/login", json={"email": "no@x.com", "password": "x"}
        )
        r2 = await c.post(
            "/auth/login",
            json={"email": "u1@example.com", "password": "wrong"},
        )
        assert r1.status_code == r2.status_code == 401
        assert r1.json()["detail"] == r2.json()["detail"]
