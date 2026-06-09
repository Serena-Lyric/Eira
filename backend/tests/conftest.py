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
    # Clear settings cache so tests can override env vars
    get_settings.cache_clear()

    # Disable rate limiting in tests (§5.4 — tests share a single IP and
    # would hit the auth rate limiter after a few test registrations).
    import os
    os.environ["EIRA_RATE_LIMIT__ENABLED"] = "false"


@pytest.fixture
async def admin_session():
    """Bootstrap an admin user directly in the DB and return tokens + info.

    This fixture bypasses the API to create the first admin — there is no
    self-promotion endpoint (correctly, for security).  Tests that need an
    admin to exercise admin-scoped endpoints should use this fixture.
    """
    from app.infra.db import get_session_factory
    from app.domain.identity.models import User
    from app.domain.identity.repository import UserRepository
    from app.domain.identity.service import IdentityService
    from app.core.security import hash_password, issue_token

    factory = get_session_factory()
    async with factory() as session:
        repo = UserRepository(session)
        svc = IdentityService(repo)

        email = f"admin-{uuid.uuid4().hex[:8]}@example.com"
        u = User(
            email=email,
            password_hash=hash_password("Passw0rd!"),
            display_name=f"Admin-{email[:6]}",
            role="admin",
            status="active",
        )
        session.add(u)
        await session.commit()
        await session.refresh(u)

        access = issue_token(str(u.id), u.role, "access")
        refresh = issue_token(str(u.id), u.role, "refresh")

        return {
            "access_token": access,
            "refresh_token": refresh,
            "token_type": "bearer",
            "user": {
                "id": u.id,
                "email": email,
                "role": "admin",
                "display_name": u.display_name,
            },
        }
