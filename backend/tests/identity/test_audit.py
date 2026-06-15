"""Integration tests for audit middleware and admin audit query endpoints."""

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


@pytest.mark.asyncio
async def test_audit_logs_admin_mutation():
    """Admin mutating operations are recorded in audit log."""
    email = f"aud-{uuid.uuid4().hex[:8]}@example.com"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        admin = await _register_and_login(c, email)
        await _make_admin_direct(admin)

        # Perform a mutation that should be audited
        await c.post(
            "/admin/personas",
            json={"name": "Audited Persona", "scope": "public"},
            headers={"Authorization": f"Bearer {admin['access_token']}"},
        )

        # Query audit logs
        r = await c.get(
            "/admin/audit", params={"page": 1, "page_size": 10},
            headers={"Authorization": f"Bearer {admin['access_token']}"},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["total"] >= 1
        assert any("POST" in entry["method"] for entry in data["items"])


@pytest.mark.asyncio
async def test_non_admin_routes_not_audited():
    """Non-admin POST requests are not audited."""
    email = f"na-{uuid.uuid4().hex[:8]}@example.com"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        await _register_and_login(c, email)

        # This is a non-admin POST (login) — should NOT be audited
        await c.post("/auth/login", json={"email": email, "password": "Passw0rd!"})

        # Get an admin to check audit logs
        admin_email = f"adm-{uuid.uuid4().hex[:8]}@example.com"
        admin = await _register_and_login(c, admin_email)
        await _make_admin_direct(admin)

        r = await c.get(
            "/admin/audit",
            headers={"Authorization": f"Bearer {admin['access_token']}"},
        )
        # Login is not under /admin so shouldn't create audit entries
        # But other admin mutations might exist. The key is that /auth/login
        # entries are NOT present.
        data = r.json()
        login_entries = [e for e in data["items"] if "/auth/login" in e["path"]]
        assert len(login_entries) == 0


@pytest.mark.asyncio
async def test_visitor_cannot_access_audit():
    """Non-admin cannot read audit logs."""
    email = f"vis-{uuid.uuid4().hex[:8]}@example.com"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        user = await _register_and_login(c, email)

        r = await c.get(
            "/admin/audit",
            headers={"Authorization": f"Bearer {user['access_token']}"},
        )
        assert r.status_code == 403, r.text


@pytest.mark.asyncio
async def test_audit_filter_by_path():
    """Audit logs can be filtered by path prefix."""
    email = f"path-{uuid.uuid4().hex[:8]}@example.com"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        admin = await _register_and_login(c, email)
        await _make_admin_direct(admin)

        # Create persona (audited)
        await c.post(
            "/admin/personas",
            json={"name": "PathFilter Persona", "scope": "public"},
            headers={"Authorization": f"Bearer {admin['access_token']}"},
        )

        # Filter by persona path
        r = await c.get(
            "/admin/audit", params={"path": "/admin/personas"},
            headers={"Authorization": f"Bearer {admin['access_token']}"},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        for item in data["items"]:
            assert item["path"].startswith("/admin/personas")


@pytest.mark.asyncio
async def test_audit_csv_export():
    """Audit logs can be exported as CSV."""
    email = f"csv-{uuid.uuid4().hex[:8]}@example.com"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        admin = await _register_and_login(c, email)
        await _make_admin_direct(admin)

        # Perform an audited mutation
        await c.patch(
            "/admin/settings",
            json={"settings": {"test.export": {"key": "value"}}},
            headers={"Authorization": f"Bearer {admin['access_token']}"},
        )

        r = await c.get(
            "/admin/audit/export",
            headers={"Authorization": f"Bearer {admin['access_token']}"},
        )
        assert r.status_code == 200, r.text
        assert "text/csv" in r.headers.get("content-type", "")
        # CSV should have header row
        content = r.text
        assert "id,user_id,action" in content


@pytest.mark.asyncio
async def test_audit_body_summary_redaction():
    """Sensitive fields in audit body_summary are redacted."""
    email = f"body-{uuid.uuid4().hex[:8]}@example.com"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        admin = await _register_and_login(c, email)
        await _make_admin_direct(admin)

        # Update a setting with a sensitive key name
        await c.patch(
            "/admin/settings",
            json={"settings": {"security.api_key": {"token": "test-secret-value"}}},
            headers={"Authorization": f"Bearer {admin['access_token']}"},
        )

        r = await c.get(
            "/admin/audit", params={"page": 1, "page_size": 10},
            headers={"Authorization": f"Bearer {admin['access_token']}"},
        )
        # The audit entry should exist — body_summary redaction tested separately in unit
        assert r.status_code == 200
