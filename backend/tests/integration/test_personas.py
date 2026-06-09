"""Integration tests for persona CRUD endpoints (user + admin)."""

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


async def _make_admin_direct(admin_dict: dict) -> None:
    """Promote a user to admin directly in DB, update admin_dict tokens in-place."""
    from app.infra.db import get_session_factory
    from app.domain.identity.repository import UserRepository
    from app.core.security import issue_token

    uid = admin_dict["user"]["id"]
    factory = get_session_factory()
    async with factory() as session:
        repo = UserRepository(session)
        u = await repo.get_by_id(uid)
        u.role = "admin"
        await session.commit()
        admin_dict["access_token"] = issue_token(str(u.id), "admin", "access")
        admin_dict["user"]["role"] = "admin"


# ── User-facing persona CRUD ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_user_create_and_list_own_persona():
    """A user can create a user-scoped persona and see it in their list."""
    email = f"p-{uuid.uuid4().hex[:8]}@example.com"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        user = await _register_and_login(c, email)

        # Create persona
        r = await c.post(
            "/personas",
            json={"name": "Test Character", "scope": "user", "description": "A test persona"},
            headers={"Authorization": f"Bearer {user['access_token']}"},
        )
        assert r.status_code == 201, r.text
        persona = r.json()
        assert persona["name"] == "Test Character"
        assert persona["scope"] == "user"

        # List personas
        r = await c.get(
            "/personas",
            headers={"Authorization": f"Bearer {user['access_token']}"},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert any(p["id"] == persona["id"] for p in data["items"])


@pytest.mark.asyncio
async def test_user_cannot_create_public_persona():
    """A regular user cannot create a public persona."""
    email = f"pub-{uuid.uuid4().hex[:8]}@example.com"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        user = await _register_and_login(c, email)

        r = await c.post(
            "/personas",
            json={"name": "Public Char", "scope": "public"},
            headers={"Authorization": f"Bearer {user['access_token']}"},
        )
        assert r.status_code == 403, r.text


@pytest.mark.asyncio
async def test_user_patch_and_delete_own_persona():
    """A user can update and soft-delete their own persona."""
    email = f"p-{uuid.uuid4().hex[:8]}@example.com"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        user = await _register_and_login(c, email)

        r = await c.post(
            "/personas",
            json={"name": "Original", "scope": "user"},
            headers={"Authorization": f"Bearer {user['access_token']}"},
        )
        persona_id = r.json()["id"]

        # Patch
        r = await c.patch(
            f"/personas/{persona_id}",
            json={"name": "Updated"},
            headers={"Authorization": f"Bearer {user['access_token']}"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["name"] == "Updated"

        # Delete
        r = await c.delete(
            f"/personas/{persona_id}",
            headers={"Authorization": f"Bearer {user['access_token']}"},
        )
        assert r.status_code == 204, r.text


@pytest.mark.asyncio
async def test_user_cannot_access_others_user_persona():
    """User A cannot access user B's user-scoped persona."""
    email_a = f"a-{uuid.uuid4().hex[:8]}@example.com"
    email_b = f"b-{uuid.uuid4().hex[:8]}@example.com"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        user_a = await _register_and_login(c, email_a)
        user_b = await _register_and_login(c, email_b)

        r = await c.post(
            "/personas",
            json={"name": "B's Secret", "scope": "user"},
            headers={"Authorization": f"Bearer {user_b['access_token']}"},
        )
        persona_id = r.json()["id"]

        # User A tries to get user B's persona
        r = await c.get(
            f"/personas/{persona_id}",
            headers={"Authorization": f"Bearer {user_a['access_token']}"},
        )
        assert r.status_code == 403, r.text


# ── Admin persona CRUD ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_admin_list_all_personas():
    """Admin can see all personas including disabled ones."""
    email = f"adm-{uuid.uuid4().hex[:8]}@example.com"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        admin = await _register_and_login(c, email)
        await _make_admin_direct(admin)

        r = await c.get(
            "/admin/personas",
            headers={"Authorization": f"Bearer {admin['access_token']}"},
        )
        assert r.status_code == 200, r.text
        assert "items" in r.json()


@pytest.mark.asyncio
async def test_admin_create_and_set_default_persona():
    """Admin can create a public persona and set it as default."""
    email = f"adm-{uuid.uuid4().hex[:8]}@example.com"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        admin = await _register_and_login(c, email)
        await _make_admin_direct(admin)

        r = await c.post(
            "/admin/personas",
            json={"name": "Admin Public", "scope": "public", "personality": "Friendly"},
            headers={"Authorization": f"Bearer {admin['access_token']}"},
        )
        assert r.status_code == 201, r.text
        persona_id = r.json()["id"]

        # Set as default
        r = await c.post(
            f"/admin/personas/{persona_id}/set-default",
            headers={"Authorization": f"Bearer {admin['access_token']}"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["is_default"] is True


@pytest.mark.asyncio
async def test_admin_delete_persona():
    """Admin can soft-delete a persona."""
    email = f"adm-{uuid.uuid4().hex[:8]}@example.com"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        admin = await _register_and_login(c, email)
        await _make_admin_direct(admin)

        r = await c.post(
            "/admin/personas",
            json={"name": "ToDelete", "scope": "public"},
            headers={"Authorization": f"Bearer {admin['access_token']}"},
        )
        persona_id = r.json()["id"]

        r = await c.delete(
            f"/admin/personas/{persona_id}",
            headers={"Authorization": f"Bearer {admin['access_token']}"},
        )
        assert r.status_code == 204, r.text


# ── Import / Export ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_import_export_sillytavern_v2():
    """User can import a ST V2 JSON and export it back."""
    email = f"st-{uuid.uuid4().hex[:8]}@example.com"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        user = await _register_and_login(c, email)

        st_json = {
            "data": {
                "name": "ST Import Test",
                "description": "Imported character",
                "personality": "Cheerful and helpful",
                "scenario": "Tourist information desk",
                "first_mes": "Hello! How can I help you today?",
                "mes_example": "<START>\n{{char}}: Welcome!\n{{user}}: Hi\n",
                "system_prompt": "You are a helpful assistant.",
                "tags": ["tour-guide", "friendly"],
            }
        }

        # Import
        r = await c.post(
            "/personas/import",
            json={"data": st_json, "scope": "user"},
            headers={"Authorization": f"Bearer {user['access_token']}"},
        )
        assert r.status_code == 201, r.text
        persona = r.json()
        assert persona["name"] == "ST Import Test"
        assert persona["personality"] == "Cheerful and helpful"
        assert "tour-guide" in persona["tags"]

        # Export
        r = await c.get(
            f"/personas/{persona['id']}/export",
            headers={"Authorization": f"Bearer {user['access_token']}"},
        )
        assert r.status_code == 200, r.text
        exported = r.json()
        assert "data" in exported
        assert exported["data"]["name"] == "ST Import Test"
