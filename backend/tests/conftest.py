import sys
import asyncio
import uuid
import warnings
import pytest

if sys.platform == "win32":
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        except AttributeError:
            pass


# ── Session-scoped cleanup: remove all test data after the run ───────────────

@pytest.fixture(scope="session", autouse=True)
async def _cleanup_test_data():
    """After all tests complete, delete test-created rows from every table
    that integration tests write to, and restore the real default persona.

    This is a session-scoped fixture so it runs exactly once per pytest
    invocation — yields during collection/execution, cleans up at teardown.
    """
    yield  # — all tests run here —

    from sqlalchemy import text
    from app.infra.db import get_engine

    engine = get_engine()
    async with engine.connect() as conn:
        # Wrap in a transaction so cleanup is atomic
        async with conn.begin() as tx:
            # Order matters — delete children before parents (FK constraints)
            # 1. chat_message → chat_session
            await conn.execute(text(
                "DELETE FROM chat_message WHERE session_id IN "
                "(SELECT id FROM chat_session WHERE user_id IN "
                "(SELECT id FROM users WHERE email LIKE '%%@example.com'))"
            ))
            await conn.execute(text(
                "DELETE FROM chat_session WHERE user_id IN "
                "(SELECT id FROM users WHERE email LIKE '%%@example.com')"
            ))

            # 2. feedback → users
            await conn.execute(text(
                "DELETE FROM feedback WHERE user_id IN "
                "(SELECT id FROM users WHERE email LIKE '%%@example.com')"
            ))

            # 3. audit_log (generic target_type/target_id, no FK)
            await conn.execute(text(
                "DELETE FROM audit_log WHERE target_id NOT IN (SELECT id FROM users)"
            ))

            # 4. knowledge_chunks → documents (documents uses uploader_id, not user_id)
            await conn.execute(text(
                "DELETE FROM knowledge_chunks WHERE document_id IN "
                "(SELECT id FROM documents WHERE uploader_id IN "
                "(SELECT id FROM users WHERE email LIKE '%%@example.com'))"
            ))
            await conn.execute(text(
                "DELETE FROM documents WHERE uploader_id IN "
                "(SELECT id FROM users WHERE email LIKE '%%@example.com')"
            ))

            # 5. assets → users
            await conn.execute(text(
                "DELETE FROM assets WHERE user_id IN "
                "(SELECT id FROM users WHERE email LIKE '%%@example.com')"
            ))

            # 6. personas (keep id=229, the real 灵山胜境导游)
            await conn.execute(text("DELETE FROM personas WHERE id != 229"))
            await conn.execute(text(
                "UPDATE personas SET is_default = true WHERE id = 229"
            ))

            # 7. users — last (all child rows already deleted)
            await conn.execute(text(
                "DELETE FROM users WHERE email LIKE '%%@example.com'"
            ))


# ── Shared LRU-cache & env cleanup ─────────────────────────────────────────

@pytest.fixture(autouse=True)
def _clear_lru_caches():
    from app.infra.db import get_engine, get_session_factory
    from app.infra.redis import get_redis
    from app.infra.oss import get_oss_client
    from app.core.config import get_settings

    get_engine.cache_clear()
    get_session_factory.cache_clear()
    get_redis.cache_clear()
    get_oss_client.cache_clear()
    get_settings.cache_clear()

    import os
    os.environ["EIRA_RATE_LIMIT__ENABLED"] = "false"
    if not os.environ.get("EIRA_OSS__SECRET"):
        os.environ["EIRA_OSS__SECRET"] = "eira-secret"


# ── HTTP client fixtures (with pre-bootstrapped users) ─────────────────────

def _build_async_client():
    """Return an httpx.AsyncClient wired to the FastAPI app via ASGI transport."""
    from httpx import AsyncClient, ASGITransport
    from app.main import app
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.fixture
async def client():
    """Bare async HTTP client — no auth."""
    async with _build_async_client() as c:
        yield c


@pytest.fixture
async def admin_session(client):
    """HTTP client pre-authenticated as an admin user.

    The test user is cleaned up after the session by _cleanup_test_data.
    """
    from app.domain.identity.models import User
    from app.domain.identity.repository import UserRepository
    from app.infra.db import get_session_factory
    from app.core.security import hash_password, issue_token

    factory = get_session_factory()
    async with factory() as session:
        repo = UserRepository(session)
        email = f"admin-{uuid.uuid4().hex[:8]}@example.com"
        u = User(
            email=email,
            password_hash=hash_password("Passw0rd!"),
            display_name=f"Admin-{email[:6]}",
            role="admin",
            status="active",
        )
        session.add(u)
        await session.flush()
        await session.refresh(u)

        token = issue_token(str(u.id), u.role, "access")
        client.headers["Authorization"] = f"Bearer {token}"

        yield {
            "client": client,
            "token": token,
            "user_id": u.id,
            "user": {"id": u.id, "email": email, "role": "admin", "display_name": u.display_name},
        }
        # No manual cleanup needed — cleanup_test_data handles it


@pytest.fixture
async def user_session(client):
    """HTTP client pre-authenticated as a regular user."""
    from app.domain.identity.models import User
    from app.domain.identity.repository import UserRepository
    from app.infra.db import get_session_factory
    from app.core.security import hash_password, issue_token

    factory = get_session_factory()
    async with factory() as session:
        repo = UserRepository(session)
        email = f"user-{uuid.uuid4().hex[:8]}@example.com"
        u = User(
            email=email,
            password_hash=hash_password("Passw0rd!"),
            display_name=f"User-{email[:6]}",
            role="user",
            status="active",
        )
        session.add(u)
        await session.flush()
        await session.refresh(u)

        token = issue_token(str(u.id), u.role, "access")
        client.headers["Authorization"] = f"Bearer {token}"

        yield {
            "client": client,
            "token": token,
            "user_id": u.id,
        }
