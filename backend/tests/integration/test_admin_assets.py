"""Integration tests for admin asset management endpoints (P0-2 fix)."""

import io
import uuid
import zipfile

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _register_and_login(client: AsyncClient) -> tuple[str, int]:
    email = f"admin-asset-{uuid.uuid4().hex[:8]}@example.com"
    r = await client.post(
        "/auth/register",
        json={"email": email, "password": "Passw0rd!", "display_name": "AAT"},
    )
    assert r.status_code == 201, r.text
    uid = r.json()["id"]
    r = await client.post("/auth/login", json={"email": email, "password": "Passw0rd!"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"], uid


async def _bootstrap_admin(c: AsyncClient) -> tuple[str, int]:
    """Create the first admin by directly inserting into DB."""
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
        uid = row[0]
        await conn.commit()

    r = await c.post("/auth/login", json={"email": email, "password": "Passw0rd!"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"], uid


async def _make_admin(c: AsyncClient, admin_token: str, uid: int) -> None:
    r = await c.patch(
        f"/admin/users/{uid}",
        json={"role": "admin"},
        headers=_bearer(admin_token),
    )
    assert r.status_code == 200, r.text


async def _upload_background(c: AsyncClient, token: str) -> int:
    """Upload a test background and return its asset_id."""
    jpeg = (
        b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
        b"\xff\xdb\x00C\x00\x03\x02\x02\x02\x02\x02\x03\x02\x02\x02\x03\x03\x03"
        b"\x03\x04\x06\x04\x04\x04\x04\x04\x08\x06\x06\x05\x06\t\n\n\t\t\t\t\t"
        b"\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f"
        b"\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xc4\x00\xb5\x10\x00"
        b"\x02\x01\x03\x03\x02\x04\x03\x05\x05\x04\x04\x00\x00\x01}\x01\x02\x03"
        b"\x00\x04\x11\x05\x12!1A\x06\x13Qa\x07\"q\x142\x81\x91\xa1\x08#B\xb1"
        b"\xff\xda\x00\x08\x01\x01\x00\x00?\x00\x1f\x00\x00\x00\x00\x00\x00\xff\xd9"
    )
    r = await c.post(
        "/assets/backgrounds",
        files={"file": (f"bg-{uuid.uuid4().hex[:6]}.jpg", jpeg, "image/jpeg")},
        headers=_bearer(token),
    )
    assert r.status_code == 201, r.text
    return r.json()["asset_id"]


async def _upload_live2d(c: AsyncClient, token: str) -> int:
    """Upload a test Live2D model zip and return its asset_id."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("model3.json", '{"Version":3,"FileReferences":{"Moc":"model.moc3"}}')
    valid_zip = buf.getvalue()

    r = await c.post(
        "/assets/live2d",
        files={"file": (f"model-{uuid.uuid4().hex[:6]}.zip", valid_zip, "application/zip")},
        headers=_bearer(token),
    )
    assert r.status_code == 201, r.text
    return r.json()["asset_id"]


# ── List (admin) ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_admin_assets_empty():
    """P0-2: New admin gets empty asset list with correct format."""
    email = f"admin-empty-{uuid.uuid4().hex[:8]}@example.com"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        token, uid = await _bootstrap_admin(c)

        r = await c.get("/admin/assets", headers=_bearer(token))
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data["items"], list)
        assert isinstance(data["total"], int)


@pytest.mark.asyncio
async def test_list_admin_assets_response_format():
    """P0-2: Verify response schema {items: [...], total: number} with correct fields."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        # Register a user and upload an asset
        user_token, user_uid = await _register_and_login(c)
        asset_id = await _upload_background(c, user_token)

        # Register an admin and list
        admin_token, admin_uid = await _bootstrap_admin(c)

        r = await c.get("/admin/assets", headers=_bearer(admin_token))
        assert r.status_code == 200, r.text
        data = r.json()

        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)
        assert isinstance(data["total"], int)
        assert data["total"] >= 1

        # Verify each item has the expected fields from AdminAssetOut
        required_fields = {"id", "kind", "name", "mime_type", "file_size", "user_id", "created_at"}
        for item in data["items"]:
            assert required_fields.issubset(set(item.keys())), \
                f"Item missing fields: {required_fields - set(item.keys())}"
            assert isinstance(item["id"], int)
            assert isinstance(item["kind"], str)
            assert isinstance(item["name"], str)
            assert isinstance(item["user_id"], int)


@pytest.mark.asyncio
async def test_list_admin_assets_requires_admin():
    """P0-2: Non-admin user gets 403 when accessing admin asset list."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        token, _ = await _register_and_login(c)

        r = await c.get("/admin/assets", headers=_bearer(token))
        assert r.status_code == 403, r.text


@pytest.mark.asyncio
async def test_list_admin_assets_filter_by_kind():
    """P0-2: Filter by kind=live2d_model returns only matching assets."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        user_token, user_uid = await _register_and_login(c)
        # Upload one of each kind
        await _upload_background(c, user_token)
        await _upload_live2d(c, user_token)

        # Admin lists with kind filter
        admin_token, admin_uid = await _bootstrap_admin(c)

        r = await c.get("/admin/assets", params={"kind": "live2d_model"}, headers=_bearer(admin_token))
        assert r.status_code == 200, r.text
        data = r.json()

        for item in data["items"]:
            assert item["kind"] == "live2d_model", f"Filtered item has wrong kind: {item['kind']}"


# ── Delete (admin) ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_admin_asset():
    """P0-2: Admin can delete any asset."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        user_token, user_uid = await _register_and_login(c)
        asset_id = await _upload_background(c, user_token)

        admin_token, admin_uid = await _bootstrap_admin(c)

        r = await c.delete(f"/admin/assets/{asset_id}", headers=_bearer(admin_token))
        assert r.status_code == 200, r.text
        assert r.json()["success"] is True

        # Verify it's gone from the list
        r = await c.get("/admin/assets", headers=_bearer(admin_token))
        assert r.status_code == 200
        ids = [item["id"] for item in r.json()["items"]]
        assert asset_id not in ids


@pytest.mark.asyncio
async def test_delete_admin_asset_not_found():
    """P0-2: Delete non-existent asset returns 404."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        token, uid = await _bootstrap_admin(c)

        r = await c.delete("/admin/assets/99999", headers=_bearer(token))
        assert r.status_code == 404, r.text
