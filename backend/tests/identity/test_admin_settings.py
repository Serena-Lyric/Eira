"""Integration tests for admin system settings endpoints."""

import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


async def _register_and_login(client: AsyncClient, email: str) -> dict:
    r = await client.post(
        "/auth/register",
        json={"email": email, "password": "Passw0rd!", "display_name": f"U-{email[:6]}"},
    )
    assert r.status_code == 201, r.text
    r = await client.post("/auth/login", json={"email": email, "password": "Passw0rd!"})
    assert r.status_code == 200, r.text
    tokens = r.json()
    r = await client.get("/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    return {**tokens, "user": r.json()}


async def _bootstrap_admin(client: AsyncClient) -> dict:
    """Create the first admin by directly inserting into DB (no admin needed)."""
    from sqlalchemy import text
    from app.infra.db import get_engine
    from app.core.security import hash_password

    email = f"admin-{uuid.uuid4().hex[:8]}@example.com"
    pwd_hash = hash_password("Passw0rd!")
    engine = get_engine()
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                "INSERT INTO users (email, password_hash, display_name, role, status) "
                "VALUES (:email, :pwd, :dn, 'admin', 'active') RETURNING id"
            ),
            {"email": email, "pwd": pwd_hash, "dn": f"Admin-{email[:6]}"},
        )
        row = result.fetchone()
        await conn.commit()

    r = await client.post("/auth/login", json={"email": email, "password": "Passw0rd!"})
    assert r.status_code == 200, r.text
    tokens = r.json()
    r = await client.get("/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    return {**tokens, "user": r.json()}


async def _make_admin(client: AsyncClient, admin_tokens: dict, uid: int) -> None:
    r = await client.patch(
        f"/admin/users/{uid}", json={"role": "admin"},
        headers={"Authorization": f"Bearer {admin_tokens['access_token']}"},
    )
    assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_get_empty_settings():
    """Admin can get settings (empty initially)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        admin = await _bootstrap_admin(c)

        r = await c.get(
            "/admin/settings",
            headers={"Authorization": f"Bearer {admin['access_token']}"},
        )
        assert r.status_code == 200, r.text
        assert "settings" in r.json()


@pytest.mark.asyncio
async def test_set_and_get_setting():
    """Admin can update and retrieve a setting."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        admin = await _bootstrap_admin(c)

        # Upsert via batch
        r = await c.patch(
            "/admin/settings",
            json={"settings": {"llm.default_model": {"provider": "deepseek", "model": "deepseek-chat"}}},
            headers={"Authorization": f"Bearer {admin['access_token']}"},
        )
        assert r.status_code == 200, r.text
        assert "llm.default_model" in r.json()["settings"]

        # Get single
        r = await c.get(
            "/admin/settings/llm.default_model",
            headers={"Authorization": f"Bearer {admin['access_token']}"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["provider"] == "deepseek"


@pytest.mark.asyncio
async def test_api_key_redaction():
    """Sensitive keys are redacted from responses."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        admin = await _bootstrap_admin(c)

        await c.patch(
            "/admin/settings",
            json={"settings": {"llm.api_key": {"token": "sk-super-secret"}}},
            headers={"Authorization": f"Bearer {admin['access_token']}"},
        )

        r = await c.get(
            "/admin/settings/llm.api_key",
            headers={"Authorization": f"Bearer {admin['access_token']}"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["token"] == "***"


@pytest.mark.asyncio
async def test_patch_single_setting():
    """Admin can update a single setting key."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        admin = await _bootstrap_admin(c)

        r = await c.patch(
            "/admin/settings/quota.background",
            json={"limit": 5, "per_user": True},
            headers={"Authorization": f"Bearer {admin['access_token']}"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["limit"] == 5


@pytest.mark.asyncio
async def test_visitor_cannot_access_settings():
    """Non-admin cannot access settings."""
    email = f"vis-{uuid.uuid4().hex[:8]}@example.com"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        user = await _register_and_login(c, email)

        r = await c.get(
            "/admin/settings",
            headers={"Authorization": f"Bearer {user['access_token']}"},
        )
        assert r.status_code == 403, r.text


# ── P0-1: Flat-value settings (non-dict values) ─────────────────────────


@pytest.mark.asyncio
async def test_patch_flat_string_values():
    """P0-1: Admin can save flat string values (not nested dicts)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        admin = await _bootstrap_admin(c)

        r = await c.patch(
            "/admin/settings",
            json={"settings": {"llm_provider": "deepseek", "llm_model": "deepseek-chat"}},
            headers={"Authorization": f"Bearer {admin['access_token']}"},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["settings"]["llm_provider"] == "deepseek"
        assert data["settings"]["llm_model"] == "deepseek-chat"


@pytest.mark.asyncio
async def test_patch_flat_mixed_values():
    """P0-1: Admin can save mixed flat values (string, int, bool)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        admin = await _bootstrap_admin(c)

        r = await c.patch(
            "/admin/settings",
            json={
                "settings": {
                    "daily_search_quota": 200,
                    "voice_persistence": True,
                    "global_background_url": "https://example.com/bg.jpg",
                    "user_doc_quota": 100,
                }
            },
            headers={"Authorization": f"Bearer {admin['access_token']}"},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["settings"]["daily_search_quota"] == 200
        assert data["settings"]["voice_persistence"] is True
        assert data["settings"]["global_background_url"] == "https://example.com/bg.jpg"
        assert data["settings"]["user_doc_quota"] == 100


@pytest.mark.asyncio
async def test_get_settings_roundtrip_flat_values():
    """P0-1: Write flat values then read them back correctly."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        admin = await _bootstrap_admin(c)

        # Write flat values
        r = await c.patch(
            "/admin/settings",
            json={"settings": {"tts_engine": "aliyun_nls", "asr_engine": "aliyun_asr"}},
            headers={"Authorization": f"Bearer {admin['access_token']}"},
        )
        assert r.status_code == 200, r.text

        # Read them back
        r = await c.get(
            "/admin/settings",
            headers={"Authorization": f"Bearer {admin['access_token']}"},
        )
        assert r.status_code == 200, r.text
        settings = r.json()["settings"]
        assert settings["tts_engine"] == "aliyun_nls"
        assert settings["asr_engine"] == "aliyun_asr"


@pytest.mark.asyncio
async def test_patch_flat_and_dict_values_coexist():
    """P0-1: Flat values and nested dict values can coexist in the same request."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        admin = await _bootstrap_admin(c)

        r = await c.patch(
            "/admin/settings",
            json={
                "settings": {
                    "llm_provider": "deepseek",                           # flat string
                    "api_key_status": {"deepseek": "configured"},         # nested dict
                    "daily_search_quota": 200,                            # flat int
                }
            },
            headers={"Authorization": f"Bearer {admin['access_token']}"},
        )
        assert r.status_code == 200, r.text
        data = r.json()["settings"]
        assert data["llm_provider"] == "deepseek"
        assert data["daily_search_quota"] == 200
        assert data["api_key_status"]["deepseek"] == "configured"
