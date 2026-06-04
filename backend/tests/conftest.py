import sys
import asyncio
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
    get_settings.cache_clear()
