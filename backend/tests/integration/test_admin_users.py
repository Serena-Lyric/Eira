"""Integration tests for admin user management endpoints."""

import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


async def _register_and_login(client: AsyncClient, email: str, role: str = "visitor") -> dict:
    """Helper: register a user and return tokens + user info."""
    r = await client.post(
        "/auth/register",
        json={"email": email, "password": "Passw0rd!", "display_name": f"User-{email[:6]}"},
    )
    assert r.status_code == 201, r.text
    r = await client.post("/auth/login", json={"email": email, "password": "Passw0rd!"})
    assert r.status_code == 200, r.text
    tokens = r.json()

    r = await client.get("/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert r.status_code == 200, r.text
    return {**tokens, "user": r.json()}


async def _make_admin_direct(admin_dict: dict) -> None:
    """Promote a user to admin directly in DB, update admin_dict tokens in-place.

    Bypasses the PATCH /admin/users/{uid} endpoint because a visitor cannot
    promote themselves — there is no bootstrap admin.  Updates admin_dict
    so all subsequent references to admin['access_token'] carry admin role.
    """
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


@pytest.mark.asyncio
async def test_list_users_pagination():
    """Admin can list users with pagination."""
    email1 = f"list-{uuid.uuid4().hex[:8]}@example.com"
    email2 = f"list-{uuid.uuid4().hex[:8]}@example.com"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        admin = await _register_and_login(c, email1)
        await _make_admin_direct(admin)

        # Create another user
        await _register_and_login(c, email2)

        # List as admin
        r = await c.get(
            "/admin/users", params={"page": 1, "page_size": 10},
            headers={"Authorization": f"Bearer {admin['access_token']}"},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["total"] >= 2
        assert len(data["items"]) >= 2


@pytest.mark.asyncio
async def test_list_users_keyword_filter():
    """Admin can filter users by keyword."""
    email = f"kw-{uuid.uuid4().hex[:8]}@example.com"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        admin = await _register_and_login(c, email)
        await _make_admin_direct(admin)

        # Search by email fragment
        r = await c.get(
            "/admin/users", params={"keyword": email[:10]},
            headers={"Authorization": f"Bearer {admin['access_token']}"},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["total"] >= 1


@pytest.mark.asyncio
async def test_get_user_detail():
    """Admin can get a single user's detail."""
    email = f"detail-{uuid.uuid4().hex[:8]}@example.com"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        admin = await _register_and_login(c, email)
        await _make_admin_direct(admin)

        r = await c.get(
            f"/admin/users/{admin['user']['id']}",
            headers={"Authorization": f"Bearer {admin['access_token']}"},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["id"] == admin["user"]["id"]
        assert "disabled" in data
        assert "status" in data


@pytest.mark.asyncio
async def test_cannot_change_own_role():
    """Admin cannot change their own role."""
    email = f"ownrole-{uuid.uuid4().hex[:8]}@example.com"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        admin = await _register_and_login(c, email)
        await _make_admin_direct(admin)

        r = await c.patch(
            f"/admin/users/{admin['user']['id']}",
            json={"role": "visitor"},
            headers={"Authorization": f"Bearer {admin['access_token']}"},
        )
        assert r.status_code == 400, r.text
        assert "cannot_change_own_role" in r.json()["detail"]


@pytest.mark.asyncio
async def test_cannot_disable_self():
    """Admin cannot disable themselves."""
    email = f"selfdis-{uuid.uuid4().hex[:8]}@example.com"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        admin = await _register_and_login(c, email)
        await _make_admin_direct(admin)

        r = await c.patch(
            f"/admin/users/{admin['user']['id']}",
            json={"disabled": True},
            headers={"Authorization": f"Bearer {admin['access_token']}"},
        )
        assert r.status_code == 400, r.text
        assert "cannot_disable_self" in r.json()["detail"]


@pytest.mark.asyncio
async def test_disable_and_reenable_user():
    """Admin can disable and re-enable a user."""
    admin_email = f"adm-{uuid.uuid4().hex[:8]}@example.com"
    user_email = f"usr-{uuid.uuid4().hex[:8]}@example.com"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        admin = await _register_and_login(c, admin_email)
        await _make_admin_direct(admin)

        user = await _register_and_login(c, user_email)

        # Disable user
        r = await c.patch(
            f"/admin/users/{user['user']['id']}",
            json={"disabled": True},
            headers={"Authorization": f"Bearer {admin['access_token']}"},
        )
        assert r.status_code == 200, r.text

        # Verify disabled
        r = await c.get(
            f"/admin/users/{user['user']['id']}",
            headers={"Authorization": f"Bearer {admin['access_token']}"},
        )
        assert r.json()["disabled"] is True

        # Re-enable
        r = await c.patch(
            f"/admin/users/{user['user']['id']}",
            json={"disabled": False},
            headers={"Authorization": f"Bearer {admin['access_token']}"},
        )
        assert r.status_code == 200, r.text
        r = await c.get(
            f"/admin/users/{user['user']['id']}",
            headers={"Authorization": f"Bearer {admin['access_token']}"},
        )
        assert r.json()["disabled"] is False


@pytest.mark.asyncio
async def test_soft_delete_user():
    """Admin can soft-delete a user."""
    admin_email = f"adm-{uuid.uuid4().hex[:8]}@example.com"
    user_email = f"del-{uuid.uuid4().hex[:8]}@example.com"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        admin = await _register_and_login(c, admin_email)
        await _make_admin_direct(admin)

        user = await _register_and_login(c, user_email)

        # Create a second admin so we can delete one
        await _make_admin_direct(user)

        # Soft delete the second admin (now there are 2 admins)
        r = await c.delete(
            f"/admin/users/{user['user']['id']}",
            headers={"Authorization": f"Bearer {admin['access_token']}"},
        )
        assert r.status_code == 204, r.text

        # Verify user no longer appears in list
        r = await c.get(
            "/admin/users", params={"page": 1, "page_size": 50},
            headers={"Authorization": f"Bearer {admin['access_token']}"},
        )
        items = r.json()["items"]
        assert not any(u["id"] == user["user"]["id"] for u in items)


@pytest.mark.asyncio
async def test_visitor_cannot_access_admin_users():
    """A regular visitor cannot access admin user endpoints."""
    email = f"vis-{uuid.uuid4().hex[:8]}@example.com"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        visitor = await _register_and_login(c, email)

        r = await c.get(
            "/admin/users",
            headers={"Authorization": f"Bearer {visitor['access_token']}"},
        )
        assert r.status_code == 403, r.text


@pytest.mark.asyncio
async def test_cannot_delete_self():
    """Admin cannot soft-delete themselves."""
    email = f"selfdel-{uuid.uuid4().hex[:8]}@example.com"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        admin = await _register_and_login(c, email)
        await _make_admin_direct(admin)

        r = await c.delete(
            f"/admin/users/{admin['user']['id']}",
            headers={"Authorization": f"Bearer {admin['access_token']}"},
        )
        assert r.status_code == 400, r.text
        assert "cannot_delete_self" in r.json()["detail"]
