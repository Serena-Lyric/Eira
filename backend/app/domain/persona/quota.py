"""Asset quota management — limits per user per asset kind."""

from sqlalchemy import text

from app.infra.db import get_session_factory

# Default quotas (admin users are unlimited)
QUOTAS: dict[str, int] = {
    "background": 5,
    "live2d_model": 10,
}


async def check_quota(user_id: int, kind: str) -> bool:
    """Check if a user is within quota for the given asset kind.

    Args:
        user_id: The user's ID.
        kind: Asset kind ('background' or 'live2d_model').

    Returns:
        True if the user can upload more assets of this kind.
    """
    limit = QUOTAS.get(kind, 5)

    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            text("SELECT COUNT(*) FROM assets WHERE user_id = :uid AND kind = :kind"),
            {"uid": user_id, "kind": kind},
        )
        count = result.scalar() or 0
        return count < limit


async def get_quota_info(user_id: int, kind: str) -> dict:
    """Return quota usage info for a user and asset kind."""
    limit = QUOTAS.get(kind, 5)

    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            text("SELECT COUNT(*) FROM assets WHERE user_id = :uid AND kind = :kind"),
            {"uid": user_id, "kind": kind},
        )
        count = result.scalar() or 0

    return {
        "kind": kind,
        "used": count,
        "limit": limit,
        "available": max(0, limit - count),
    }
