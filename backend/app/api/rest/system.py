from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def root() -> dict:
    return {"service": "eira-backend", "version": "0.1.0"}
