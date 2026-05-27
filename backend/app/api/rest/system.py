from fastapi import APIRouter, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text
from app.infra.db import get_engine
from app.infra.redis import get_redis
from app.infra.oss import get_oss_client

router = APIRouter()


@router.get("/")
async def root() -> dict:
    return {"service": "eira-backend", "version": "0.1.0"}


@router.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok"}


@router.get("/readyz")
async def readyz(response: Response) -> dict:
    out = {"db": "down", "redis": "down", "oss": "down"}
    try:
        async with get_engine().connect() as conn:
            await conn.execute(text("SELECT 1"))
        out["db"] = "up"
    except Exception:
        pass
    try:
        if await get_redis().ping():  # type: ignore[misc]
            out["redis"] = "up"
    except Exception:
        pass
    try:
        get_oss_client().list_buckets()
        out["oss"] = "up"
    except Exception:
        pass
    if "down" in out.values():
        response.status_code = 503
    return out


@router.get("/metrics")
async def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
