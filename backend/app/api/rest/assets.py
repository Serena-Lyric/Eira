"""REST endpoints for asset management — backgrounds & Live2D models."""

from __future__ import annotations

import json
import structlog
import uuid
import zipfile
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db_session, get_current_user, require_admin, check_upload_rate_limit
from app.domain.identity.models import User
from app.domain.persona.quota import check_quota, get_quota_info, QUOTAS

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/assets", tags=["assets"])

ALLOWED_BG_MIME = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_MODEL_EXT = {"zip"}
MAX_BG_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_MODEL_SIZE = 200 * 1024 * 1024  # 200 MB
SIGNED_URL_TTL = 300  # 5 minutes

BUCKETS = {
    "background": "eira-backgrounds",
    "live2d_model": "eira-live2d",
}


# ── Schemas ──────────────────────────────────────────────────────────


class AssetOut(BaseModel):
    id: int
    kind: str
    name: str
    mime_type: str | None = None
    file_size: int | None = None
    created_at: str | None = None


class AssetUploadOut(BaseModel):
    success: bool = True
    asset_id: int
    message: str = "上传成功"


class AssetListOut(BaseModel):
    items: list[AssetOut]
    total: int


class AssetUrlOut(BaseModel):
    url: str
    expires_in: int = SIGNED_URL_TTL


class QuotaInfoOut(BaseModel):
    kind: str
    used: int
    limit: int
    available: int


class DeleteOut(BaseModel):
    success: bool = True


# ── Helpers ───────────────────────────────────────────────────────────


async def _upload_to_oss(kind: str, key: str, body: bytes) -> None:
    from app.infra.oss import get_oss_client

    bucket = BUCKETS.get(kind, "eira-backgrounds")
    oss = get_oss_client()
    oss.put_object(Bucket=bucket, Key=key, Body=body)


def _generate_presigned_url(key: str, bucket: str) -> str:
    from app.infra.oss import get_oss_client

    oss = get_oss_client()
    url = oss.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=SIGNED_URL_TTL,
    )
    return url


async def _insert_asset(
    db: AsyncSession,
    user_id: int,
    kind: str,
    name: str,
    oss_key: str,
    mime_type: str | None,
    file_size: int | None,
    meta: dict | None = None,
) -> int:
    result = await db.execute(
        text("""INSERT INTO assets (user_id, kind, name, oss_key, mime_type, file_size, meta)
           VALUES (:uid, :kind, :name, :oss_key, :mime, :size, :meta)
           RETURNING id"""),
        {
            "uid": user_id,
            "kind": kind,
            "name": name,
            "oss_key": oss_key,
            "mime": mime_type,
            "size": file_size,
            "meta": json.dumps(meta or {}),
        },
    )
    row = result.fetchone()
    await db.commit()
    return row[0] if row else 0


# ── Background upload ─────────────────────────────────────────────────


@router.post("/backgrounds", status_code=201, response_model=AssetUploadOut)
async def upload_background(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    _rate: None = Depends(check_upload_rate_limit),
) -> AssetUploadOut:
    """Upload a background image. Max 10MB, JPG/PNG/WebP only."""
    # Validate
    if not file.filename:
        raise HTTPException(400, "文件名不能为空")

    from app.core.file_validation import normalize_mime
    mime = normalize_mime(file.content_type or "")
    if mime not in ALLOWED_BG_MIME:
        raise HTTPException(400, f"不支持的图片格式。支持: {', '.join(sorted(ALLOWED_BG_MIME))}。收到: {file.content_type}")

    content = await file.read()
    if len(content) > MAX_BG_SIZE:
        raise HTTPException(400, "图片文件过大（最大 10 MB）")

    # Validate file header against declared MIME type
    from app.core.file_validation import validate_magic
    if not validate_magic(content, mime):
        raise HTTPException(400, "文件内容与声明的格式不匹配")

    # Check quota
    within = await check_quota(user.id, "background")
    if not within:
        limit = QUOTAS.get("background", 5)
        raise HTTPException(400, f"背景图数量已达上限（{limit} 张），请先删除旧的背景图")

    # Upload to OSS
    ext = file.filename.rsplit(".", 1)[-1] if "." in file.filename else "jpg"
    asset_id = uuid.uuid4().hex[:12]
    oss_key = f"backgrounds/{user.id}/{asset_id}.{ext}"
    await _upload_to_oss("background", oss_key, content)

    # Insert record
    asset_id_int = await _insert_asset(
        db, user.id, "background", file.filename, oss_key, mime, len(content)
    )

    return AssetUploadOut(asset_id=asset_id_int)


@router.get("/backgrounds", response_model=AssetListOut)
async def list_backgrounds(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> AssetListOut:
    """List backgrounds for the current user."""
    result = await db.execute(
        text("SELECT id, kind, name, mime_type, file_size, created_at FROM assets "
        "WHERE user_id = :uid AND kind = 'background' ORDER BY created_at DESC"),
        {"uid": user.id},
    )
    rows = result.fetchall()
    items = [
        AssetOut(
            id=r[0], kind=r[1], name=r[2], mime_type=r[3],
            file_size=r[4], created_at=str(r[5]) if r[5] else None,
        )
        for r in rows
    ]
    return AssetListOut(items=items, total=len(items))


@router.get("/backgrounds/{asset_id}/url", response_model=AssetUrlOut)
async def get_background_url(
    asset_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> AssetUrlOut:
    """Get a presigned URL for a background image."""
    result = await db.execute(
        text("SELECT oss_key, user_id FROM assets WHERE id = :id"),
        {"id": asset_id},
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(404, "资源不存在")
    oss_key, owner_id = row[0], row[1]
    if owner_id != user.id:
        raise HTTPException(404, "资源不存在")

    url = _generate_presigned_url(oss_key, "eira-backgrounds")
    return AssetUrlOut(url=url)


@router.delete("/backgrounds/{asset_id}", response_model=DeleteOut)
async def delete_background(
    asset_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> DeleteOut:
    """Delete a background image."""
    result = await db.execute(
        text("SELECT oss_key, user_id FROM assets WHERE id = :id AND kind = 'background'"),
        {"id": asset_id},
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(404, "资源不存在")
    oss_key, owner_id = row[0], row[1]
    if owner_id != user.id:
        raise HTTPException(404, "资源不存在")

    # Delete from OSS
    try:
        from app.infra.oss import get_oss_client
        oss = get_oss_client()
        oss.delete_object(Bucket="eira-backgrounds", Key=oss_key)
    except Exception as exc:
        logger.warning("oss.delete_failed", oss_key=oss_key, bucket="eira-backgrounds", error=str(exc))

    await db.execute(text("DELETE FROM assets WHERE id = :id"), {"id": asset_id})
    await db.commit()
    return DeleteOut()


# ── Live2D model upload ──────────────────────────────────────────────


@router.post("/live2d", status_code=201, response_model=AssetUploadOut)
async def upload_live2d_model(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    _rate: None = Depends(check_upload_rate_limit),
) -> AssetUploadOut:
    """Upload a Live2D model zip. Validates model3.json exists in archive."""
    if not file.filename:
        raise HTTPException(400, "文件名不能为空")

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_MODEL_EXT:
        raise HTTPException(400, "仅支持 .zip 格式")

    content = await file.read()
    if len(content) > MAX_MODEL_SIZE:
        raise HTTPException(400, "模型包过大（最大 200 MB）")

    # Validate magic number — must be a real ZIP file
    from app.core.file_validation import validate_magic
    if not validate_magic(content, "application/zip"):
        raise HTTPException(400, "文件不是有效的 zip 格式")

    # Validate zip structure — must contain model3.json
    try:
        with zipfile.ZipFile(BytesIO(content)) as zf:
            names = zf.namelist()
            has_model3 = any("model3.json" in name for name in names)
            if not has_model3:
                raise HTTPException(400, "模型包中未找到 model3.json 文件，请检查模型结构")
    except zipfile.BadZipFile:
        raise HTTPException(400, "无效的 zip 文件，无法解压")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(400, "模型包校验失败")

    # Check quota
    within = await check_quota(user.id, "live2d_model")
    if not within:
        limit = QUOTAS.get("live2d_model", 10)
        raise HTTPException(400, f"模型数量已达上限（{limit} 个），请先删除旧的模型")

    # Upload to OSS
    asset_id = uuid.uuid4().hex[:12]
    oss_key = f"live2d/{user.id}/{asset_id}/{file.filename}"
    await _upload_to_oss("live2d_model", oss_key, content)

    # Insert record
    asset_id_int = await _insert_asset(
        db, user.id, "live2d_model", file.filename, oss_key, "application/zip", len(content)
    )

    return AssetUploadOut(asset_id=asset_id_int, message=f"模型包上传成功。如需使用，请联系管理员解压部署。")


@router.get("/live2d", response_model=AssetListOut)
async def list_live2d_models(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> AssetListOut:
    """List Live2D models for the current user."""
    result = await db.execute(
        text("SELECT id, kind, name, mime_type, file_size, created_at FROM assets "
        "WHERE user_id = :uid AND kind = 'live2d_model' ORDER BY created_at DESC"),
        {"uid": user.id},
    )
    rows = result.fetchall()
    items = [
        AssetOut(
            id=r[0], kind=r[1], name=r[2], mime_type=r[3],
            file_size=r[4], created_at=str(r[5]) if r[5] else None,
        )
        for r in rows
    ]
    return AssetListOut(items=items, total=len(items))


@router.delete("/live2d/{asset_id}", response_model=DeleteOut)
async def delete_live2d_model(
    asset_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> DeleteOut:
    """Delete a Live2D model."""
    result = await db.execute(
        text("SELECT oss_key, user_id FROM assets WHERE id = :id AND kind = 'live2d_model'"),
        {"id": asset_id},
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(404, "资源不存在")
    oss_key, owner_id = row[0], row[1]
    if owner_id != user.id:
        raise HTTPException(404, "资源不存在")

    try:
        from app.infra.oss import get_oss_client
        oss = get_oss_client()
        oss.delete_object(Bucket="eira-live2d", Key=oss_key)
    except Exception as exc:
        logger.warning("oss.delete_failed", oss_key=oss_key, bucket="eira-live2d", error=str(exc))

    await db.execute(text("DELETE FROM assets WHERE id = :id"), {"id": asset_id})
    await db.commit()
    return DeleteOut()


# ── Quota ─────────────────────────────────────────────────────────────


@router.get("/quota/{kind}", response_model=QuotaInfoOut)
async def get_asset_quota(
    kind: str,
    user: User = Depends(get_current_user),
) -> QuotaInfoOut:
    """Get quota usage for an asset kind."""
    if kind not in ("background", "live2d_model"):
        raise HTTPException(400, f"未知的资源类型: {kind}")
    info = await get_quota_info(user.id, kind)
    return QuotaInfoOut(**info)
