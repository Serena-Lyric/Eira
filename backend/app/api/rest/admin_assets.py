"""Admin-facing asset management — aggregated view across all users.

Provides admin endpoints that aggregate assets across all users, unlike the
user-facing /assets endpoints which are scoped to the current user.
"""

import json
import structlog
import uuid
import zipfile
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db_session, require_admin, check_write_rate_limit, check_upload_rate_limit
from app.domain.identity.models import User
from app.domain.persona.quota import check_quota, QUOTAS


logger = structlog.get_logger(__name__)

ALLOWED_BG_MIME = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_MODEL_EXT = {"zip", "7z", "rar"}
MAX_BG_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_MODEL_SIZE = 200 * 1024 * 1024  # 200 MB

router = APIRouter(prefix="/admin/assets", tags=["admin-assets"])


# ── Schemas ──────────────────────────────────────────────────────────────

class AdminAssetOut(BaseModel):
    id: int
    kind: str
    name: str
    mime_type: str | None = None
    file_size: int | None = None
    user_id: int
    created_at: str | None = None
    is_default: bool = False
    oss_key: str | None = None


class AdminAssetListOut(BaseModel):
    items: list[AdminAssetOut]
    total: int


class AssetUploadOut(BaseModel):
    success: bool = True
    asset_id: int
    message: str = "上传成功"


class DeleteOut(BaseModel):
    success: bool = True


# ── Helpers ───────────────────────────────────────────────────────────────

BUCKETS = {
    "background": "eira-backgrounds",
    "live2d_model": "eira-live2d",
}


async def _admin_upload_to_oss(kind: str, key: str, body: bytes) -> None:
    from app.infra.oss import get_oss_client

    bucket = BUCKETS.get(kind, "eira-backgrounds")
    oss = get_oss_client()
    oss.put_object(Bucket=bucket, Key=key, Body=body)


async def _admin_insert_asset(
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


# ── List (admin: see all assets) ─────────────────────────────────────────


@router.get("", response_model=AdminAssetListOut)
async def list_assets_admin(
    kind: str | None = Query(None, description="Filter by kind: background, live2d_model"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
) -> AdminAssetListOut:
    """List all assets across all users. Admin only."""
    conditions = []
    params: dict = {}

    if kind:
        conditions.append("kind = :kind")
        params["kind"] = kind

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    offset = (page - 1) * page_size

    result = await db.execute(
        text(
            f"SELECT id, kind, name, mime_type, file_size, user_id, created_at, oss_key "
            f"FROM assets {where_clause} ORDER BY created_at DESC "
            f"LIMIT :limit OFFSET :offset"
        ),
        {**params, "limit": page_size, "offset": offset},
    )
    rows = result.fetchall()

    count_result = await db.execute(
        text(f"SELECT COUNT(*) FROM assets {where_clause}"),
        params,
    )
    total = count_result.scalar() or 0

    # Read persona_config to determine which asset is currently default
    default_model_id: str | None = None
    default_bg_oss_key: str | None = None
    try:
        from app.domain.system.service import SystemSettingService
        svc = SystemSettingService(db)
        persona = await svc.get("persona_config")
        if persona and isinstance(persona, dict):
            default_model_id = persona.get("active_model_id")
            default_bg_oss_key = persona.get("default_background_oss_key")
    except Exception:
        pass

    items = [
        AdminAssetOut(
            id=r[0], kind=r[1], name=r[2], mime_type=r[3],
            file_size=r[4], user_id=r[5],
            created_at=str(r[6]) if r[6] else None,
            is_default=(
                (r[1] == "live2d_model" and default_model_id and r[7] == default_model_id) or
                (r[1] == "background" and default_bg_oss_key and r[7] == default_bg_oss_key)
            ),
            oss_key=r[7],
        )
        for r in rows
    ]
    return AdminAssetListOut(items=items, total=total)


# ── Upload Background (admin) ────────────────────────────────────────────


@router.post("/backgrounds", status_code=201, response_model=AssetUploadOut)
async def upload_background_admin(
    file: UploadFile = File(...),
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
    _rate: None = Depends(check_upload_rate_limit),
) -> AssetUploadOut:
    """Upload a background image as admin. Max 10MB, JPG/PNG/WebP only."""
    if not file.filename:
        raise HTTPException(400, "文件名不能为空")

    from app.core.file_validation import normalize_mime
    mime = normalize_mime(file.content_type or "")
    if mime not in ALLOWED_BG_MIME:
        raise HTTPException(400, f"不支持的图片格式。支持: {', '.join(sorted(ALLOWED_BG_MIME))}。收到: {file.content_type}")

    content = await file.read()
    if len(content) > MAX_BG_SIZE:
        raise HTTPException(400, "图片文件过大（最大 10 MB）")

    from app.core.file_validation import validate_magic
    if not validate_magic(content, mime):
        raise HTTPException(400, "文件内容与声明的格式不匹配")

    ext = file.filename.rsplit(".", 1)[-1] if "." in file.filename else "jpg"
    asset_key = uuid.uuid4().hex[:12]
    oss_key = f"backgrounds/{_admin.id}/{asset_key}.{ext}"
    await _admin_upload_to_oss("background", oss_key, content)

    asset_id = await _admin_insert_asset(
        db, _admin.id, "background", file.filename, oss_key, mime, len(content)
    )

    return AssetUploadOut(asset_id=asset_id, message="背景图片上传成功")


# ── Upload Live2D Model (admin) ──────────────────────────────────────────


@router.post("/live2d", status_code=201, response_model=AssetUploadOut)
async def upload_live2d_model_admin(
    file: UploadFile = File(...),
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
    _rate: None = Depends(check_upload_rate_limit),
) -> AssetUploadOut:
    """Upload a Live2D model zip as admin. Validates model3.json exists."""
    if not file.filename:
        raise HTTPException(400, "文件名不能为空")

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_MODEL_EXT:
        raise HTTPException(400, "仅支持 .zip 格式")

    content = await file.read()
    if len(content) > MAX_MODEL_SIZE:
        raise HTTPException(400, "模型包过大（最大 200 MB）")

    from app.core.file_validation import validate_magic
    # Validate magic bytes — zip only (rar/7z pass through)
    if ext == "zip" and not validate_magic(content, "application/zip"):
        raise HTTPException(400, "文件不是有效的 zip 格式")

    # Validate model3.json exists inside the archive (zip only; rar/7z skip)
    if ext == "zip":
        try:
            with zipfile.ZipFile(BytesIO(content)) as zf:
                names = zf.namelist()
                has_model3 = any("model3.json" in name for name in names)
                if not has_model3:
                    raise HTTPException(400, "模型包中未找到 model3.json 文件，请检查模型结构")
        except zipfile.BadZipFile:
            raise HTTPException(400, "无效的 zip 文件，无法解压")

    asset_key = uuid.uuid4().hex[:12]
    oss_key = f"live2d/{_admin.id}/{asset_key}/{file.filename}"
    await _admin_upload_to_oss("live2d_model", oss_key, content)

    asset_id = await _admin_insert_asset(
        db, _admin.id, "live2d_model", file.filename, oss_key, "application/zip", len(content)
    )

    return AssetUploadOut(asset_id=asset_id, message="模型包上传成功")


# ── Set Default Asset ────────────────────────────────────────────────────


@router.post("/{asset_id}/set-default", response_model=AdminAssetOut)
async def set_default_asset_admin(
    asset_id: int,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
    _rate: None = Depends(check_write_rate_limit),
) -> AdminAssetOut:
    """Set an asset as default. Live2D model → active_model_id; background → default_background_oss_key. Admin only."""
    result = await db.execute(
        text("SELECT id, kind, name, mime_type, file_size, user_id, created_at, oss_key FROM assets WHERE id = :id"),
        {"id": asset_id},
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(404, "资源不存在")

    kind = row[1]
    oss_key = row[7]  # oss_key column
    if kind not in ("live2d_model", "background"):
        raise HTTPException(400, "仅 Live2D 模型和背景图片支持设为默认")

    from app.domain.system.service import SystemSettingService
    svc = SystemSettingService(db)
    stored = await svc.get("persona_config")
    current = stored if isinstance(stored, dict) else {}

    if kind == "live2d_model":
        # §4 fix: Store OSS key as unique identifier; strip .zip for display name
        current["active_model_id"] = oss_key
        model_name = row[2]  # filename from DB
        if model_name and model_name.lower().endswith(".zip"):
            model_name = model_name[:-4]
        current["active_model_display_name"] = model_name or f"live2d-model-{asset_id}"
    elif kind == "background":
        current["default_background_oss_key"] = oss_key

    await svc.set("persona_config", current, description="Persona Live2D & speech config")

    return AdminAssetOut(
        id=row[0], kind=row[1], name=row[2], mime_type=row[3],
        file_size=row[4], user_id=row[5],
        created_at=str(row[6]) if row[6] else None,
    )


# ── Delete (admin) ───────────────────────────────────────────────────────


@router.delete("/{asset_id}", response_model=DeleteOut)
async def delete_asset_admin(
    asset_id: int,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
    _rate: None = Depends(check_write_rate_limit),
) -> DeleteOut:
    """Delete any asset by ID. Admin only."""
    result = await db.execute(
        text("SELECT oss_key, kind FROM assets WHERE id = :id"),
        {"id": asset_id},
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(404, "资源不存在")

    oss_key, asset_kind = row[0], row[1]

    bucket_map = {"background": "eira-backgrounds", "live2d_model": "eira-live2d"}
    bucket = bucket_map.get(asset_kind, "eira-backgrounds")

    try:
        from app.infra.oss import get_oss_client
        oss = get_oss_client()
        oss.delete_object(Bucket=bucket, Key=oss_key)
    except Exception as exc:
        logger.warning("oss.delete_failed", oss_key=oss_key, bucket=bucket, error=str(exc))

    await db.execute(text("DELETE FROM assets WHERE id = :id"), {"id": asset_id})
    await db.commit()
    return DeleteOut()


# ── Download (presigned URL) ─────────────────────────────────────────────


@router.get("/{asset_id}/download")
async def get_asset_download_url(
    asset_id: int,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Generate a presigned URL for downloading an asset from OSS (§4 fix).

    Used by both admin and user clients to download Live2D model zips
    before JSZip decompression and IndexedDB caching.
    """
    result = await db.execute(
        text("SELECT oss_key, kind FROM assets WHERE id = :id"),
        {"id": asset_id},
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(404, "资源不存在")

    oss_key, kind = row[0], row[1]
    bucket = BUCKETS.get(kind, "eira-backgrounds")
    from app.infra.oss import presign_get
    url = presign_get(bucket, oss_key, expires=3600)
    return {"url": url, "expires_in": 3600}


# ── Download (backend streaming) ─────────────────────────────────────────


@router.get("/{asset_id}/file")
async def download_asset_file(
    asset_id: int,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
):
    """后端直读 OSS 字节并整体返回（供前端 Live2D 加载）。

    早期版本曾尝试 presigned URL + Vite /oss proxy 307 重定向，但
    proxy 的 changeOrigin 会改写 Host header，破坏 MinIO 的 S3v4
    签名校验。这里改回 boto3 get_object 直读（同 knowledge/service.py
    的可用模式），由后端整体返回，前端无需接触 presigned URL。
    """
    result = await db.execute(
        text("SELECT oss_key, kind, name FROM assets WHERE id = :id"),
        {"id": asset_id},
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(404, "资源不存在")

    oss_key, kind, name = row[0], row[1], row[2]
    bucket = BUCKETS.get(kind, "eira-backgrounds")

    from app.infra.oss import get_object_bytes
    from fastapi import Response

    try:
        data, content_type = get_object_bytes(bucket, oss_key)
    except Exception as e:
        logger.error("oss_read_failed", asset_id=asset_id, oss_key=oss_key, error=str(e))
        raise HTTPException(502, "OSS 读取失败")

    return Response(
        content=data,
        media_type=content_type or "application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{name}"',
            "Cache-Control": "no-store",
        },
    )


# ── Cleanup test artifacts ───────────────────────────────────────────────


class CleanupOut(BaseModel):
    success: bool = True
    deleted_count: int = 0


@router.delete("/cleanup/test-artifacts", response_model=CleanupOut)
async def cleanup_test_artifacts(
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
    _rate: None = Depends(check_write_rate_limit),
) -> CleanupOut:
    """Delete test artifacts (files < 200 bytes) from assets table and OSS. Admin only."""
    result = await db.execute(
        text("SELECT id, kind, oss_key FROM assets WHERE file_size < 200")
    )
    rows = result.fetchall()
    deleted = 0

    for row in rows:
        asset_id, kind, oss_key = row[0], row[1], row[2]
        # Delete from OSS
        try:
            from app.infra.oss import get_oss_client
            bucket_map = {"background": "eira-backgrounds", "live2d_model": "eira-live2d"}
            bucket = bucket_map.get(kind, "eira-backgrounds")
            get_oss_client().delete_object(Bucket=bucket, Key=oss_key)
        except Exception as exc:
            logger.warning("cleanup.oss_delete_failed", oss_key=oss_key, error=str(exc))
        # Delete from DB
        await db.execute(text("DELETE FROM assets WHERE id = :id"), {"id": asset_id})
        deleted += 1

    await db.commit()
    logger.info("cleanup.test_artifacts", deleted=deleted)
    return CleanupOut(deleted_count=deleted)
