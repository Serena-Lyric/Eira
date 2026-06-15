"""User data endpoints: preferences, background upload, model upload."""

import json
import os
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.deps import get_current_user, get_db_session, check_write_rate_limit, check_upload_rate_limit
from app.domain.identity.models import User
from app.domain.identity.repository import UserRepository

router = APIRouter(prefix="/user", tags=["user"])

# 允许的上传格式
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_MODEL_EXTENSIONS = {".zip", ".7z", ".rar"}
ALLOWED_MODEL_TYPES = {
    "application/zip",
    "application/x-zip-compressed",
    "application/x-7z-compressed",
    "application/x-rar-compressed",
    "application/vnd.rar",
    "application/octet-stream",
}
MAX_BG_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_MODEL_SIZE = 100 * 1024 * 1024  # 100 MB


# ── Schemas ──────────────────────────────────────────────────────────

class QuickQuestionItem(BaseModel):
    """快捷问题项：展示文本 + 实际发送到后端的请求文本。"""
    display_text: str = ""  # 前端展示的问题内容
    send_text: str = ""     # 触发时向后端发送的请求文本（为空则使用 display_text）


class UserPreferences(BaseModel):
    background_url: str | None = None
    background_blur: bool = False
    voice_enabled: bool = True
    camera_mode: str = "hidden"  # front / rear / hidden
    show_mic: bool = True
    quick_questions: list[QuickQuestionItem] = Field(default_factory=lambda: [
        QuickQuestionItem(display_text="路线怎么走？", send_text="路线怎么走？"),
        QuickQuestionItem(display_text="今天有什么表演？", send_text="今天有什么表演？"),
        QuickQuestionItem(display_text="推荐附近的美食", send_text="推荐附近的美食"),
    ])
    chat_bubble_mode: str = "center"  # center / left / hidden
    quick_questions_mode: str = "center"
    input_bar_mode: str = "center"
    active_model_id: str | None = None
    model_source: str = "default"  # "default" | "custom"
    voice_input_mode: str = "click"  # click / persistent / smart / hidden
    default_speech_rate: float = 1.0  # 默认语速倍率 (0.5 ~ 2.0)
    # §12 fix: Offline idle motion — from admin persona_config
    offline_idle_motion_group: str | None = None
    offline_idle_motion_index: int | None = None


class BackgroundUploadOut(BaseModel):
    success: bool
    message: str
    url: str | None = None


class ModelUploadOut(BaseModel):
    success: bool
    message: str
    model_id: str | None = None


class PrefsUpdateIn(BaseModel):
    """部分更新用户偏好——仅传需要修改的字段。"""
    background_url: str | None = None
    background_blur: bool | None = None
    voice_enabled: bool | None = None
    camera_mode: str | None = None
    show_mic: bool | None = None
    quick_questions: list[QuickQuestionItem] | None = None
    chat_bubble_mode: str | None = None
    quick_questions_mode: str | None = None
    input_bar_mode: str | None = None
    active_model_id: str | None = None
    model_source: str | None = None
    voice_input_mode: str | None = None
    default_speech_rate: float | None = None


# ── Endpoints ────────────────────────────────────────────────────────

@router.get("/preferences", response_model=UserPreferences, summary="获取用户偏好")
async def get_preferences(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> UserPreferences:
    """返回当前用户的偏好设置。从数据库读取，无记录时返回默认值。

    背景优先级：用户自定义 > admin 全局默认（persona_config）> 无背景。
    """
    repo = UserRepository(db)
    saved = await repo.get_preferences(user.id) or {}

    # 用户自有背景 → 动态生成 presigned URL
    user_oss_key = saved.get("background_oss_key")
    if user_oss_key and isinstance(user_oss_key, str):
        from app.infra.oss import presign_get
        try:
            saved["background_url"] = presign_get("eira-user-assets", user_oss_key, expires=3600)
        except Exception:
            pass

    # Fallback to admin persona_config for global defaults
    try:
        from app.domain.system.service import SystemSettingService
        svc = SystemSettingService(db)
        persona = await svc.get("persona_config")
        if persona and isinstance(persona, dict):
            # 用户无自定义背景 → admin 全局默认背景
            if not saved.get("background_url"):
                default_oss_key = persona.get("default_background_oss_key")
                if default_oss_key and isinstance(default_oss_key, str):
                    from app.infra.oss import presign_get
                    saved["background_url"] = presign_get("eira-backgrounds", default_oss_key, expires=3600)

            # §4 fix: active_model_id fallback (user custom > admin default)
            # 合法 OSS key 必须以 "live2d/" 开头。以下情况均视为脏值/旧格式，回退默认：
            #   - 空值
            #   - 旧显示名格式（无 "/"，如 "mao_pro_zh"）
            #   - 虚拟前缀污染（"eira-model://..."，前端误把 baseUrl 写入，见 P1 根因）
            # 注意：回退源 default_model_id 本身也必须校验，否则脏默认值（如显示名）会被赋回，
            #       导致 user 端拿显示名当 OSS key 请求 → 502（见 admin/user 标识体系裂缝）。
            def _is_valid_model_key(v) -> bool:
                return isinstance(v, str) and v.startswith("live2d/")

            current_model = saved.get("active_model_id")
            if not _is_valid_model_key(current_model):
                default_model_id = persona.get("active_model_id")
                if _is_valid_model_key(default_model_id):
                    saved["active_model_id"] = default_model_id
                else:
                    # 默认值也非法 → 不下发脏值，置空让前端显示"无可用模型"而非 502
                    saved["active_model_id"] = None

            # §12 fix: Offline idle motion fallback
            if not saved.get("offline_idle_motion_group"):
                g = persona.get("offline_idle_motion_group")
                i = persona.get("offline_idle_motion_index")
                if g:
                    saved["offline_idle_motion_group"] = g
                    saved["offline_idle_motion_index"] = i if isinstance(i, int) else None
    except Exception:
        pass

    return UserPreferences(**saved) if saved else UserPreferences()


@router.get("/model/download-url", summary="获取模型包下载 URL")
async def get_model_download_url(
    oss_key: str = Query(..., description="模型的 OSS key"),
    user: User = Depends(get_current_user),
) -> dict:
    """Generate a presigned URL for downloading a Live2D model zip (§4 fix).

    Used by web-user to download admin's default model or user's custom model.
    The oss_key is resolved from preferences (active_model_id).
    """
    from app.infra.oss import presign_get
    url = presign_get("eira-live2d", oss_key, expires=3600)
    return {"url": url, "expires_in": 3600}


@router.get("/model/file", summary="后端直读模型包字节")
async def download_model_file(
    oss_key: str = Query(..., description="模型的 OSS key"),
    user: User = Depends(get_current_user),
):
    """后端直读 OSS 模型包字节并整体返回（供 web-user Live2D 加载）。

    对称于 admin /admin/assets/{id}/file。绕开 presigned URL 经 Vite
    /oss proxy 转发时 changeOrigin 改写 Host 导致的 MinIO 签名校验失败。
    """
    from app.infra.oss import get_object_bytes
    from fastapi import Response

    try:
        data, content_type = get_object_bytes("eira-live2d", oss_key)
    except Exception:
        raise HTTPException(status_code=502, detail="OSS 读取失败")

    return Response(
        content=data,
        media_type=content_type or "application/zip",
        headers={"Cache-Control": "no-store"},
    )


@router.patch("/preferences", summary="部分更新用户偏好")
async def update_preferences(
    updates: PrefsUpdateIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    _rate: None = Depends(check_write_rate_limit),
) -> dict:
    """部分更新用户偏好设置，仅传需要修改的字段。持久化到数据库。"""
    repo = UserRepository(db)
    saved = await repo.get_preferences(user.id)
    current = saved if saved else {}

    # 合并更新：只覆盖传入的非 None 字段
    update_dict = updates.model_dump(exclude_none=True)
    current.update(update_dict)

    await repo.save_preferences(user.id, current)
    return {"success": True, "message": "偏好已更新"}


@router.post("/background", response_model=BackgroundUploadOut, summary="上传背景图片")
async def upload_background(
    background: UploadFile = File(..., description="背景图片文件"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    _rate: None = Depends(check_upload_rate_limit),
) -> BackgroundUploadOut:
    """上传用户自定义背景图片。

    仅接受 JPG / PNG / WebP 格式，最大 10 MB。
    上传成功后返回图片存储 URL。
    """
    # 验证文件存在
    if not background.filename:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="未选择文件",
        )

    # 验证文件类型
    from app.core.file_validation import normalize_mime
    content_type = normalize_mime(background.content_type or "")
    ext = os.path.splitext(background.filename)[1].lower()

    if content_type not in ALLOWED_IMAGE_TYPES and ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的图片格式。仅接受 JPG、PNG、WebP。收到: {content_type or ext}",
        )

    # 验证文件大小
    contents = await background.read()
    if len(contents) > MAX_BG_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"图片文件过大。最大允许 10 MB，收到 {len(contents) / 1024 / 1024:.1f} MB",
        )

    # Validate magic number against declared MIME type (§5.5)
    from app.core.file_validation import validate_magic
    if not validate_magic(contents, content_type):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="文件内容与声明的格式不匹配",
        )

    # Upload to OSS
    from app.infra.oss import get_oss_client

    oss_bucket = "eira-user-assets"
    oss_key = f"backgrounds/{user.id}/{uuid.uuid4().hex}{ext}"
    oss = get_oss_client()
    oss.put_object(Bucket=oss_bucket, Key=oss_key, Body=contents, ContentType=content_type)

    # Generate presigned URL for client access
    from app.infra.oss import presign_get

    url = presign_get(oss_bucket, oss_key, expires=3600)

    # 持久化 OSS key 到用户偏好（而非过期 URL），防止刷新丢失
    repo = UserRepository(db)
    saved = await repo.get_preferences(user.id)
    current = saved if saved else {}
    current["background_oss_key"] = oss_key
    current["background_url"] = url  # 即时返回的 URL（下次读取时动态生成）
    await repo.save_preferences(user.id, current)

    return BackgroundUploadOut(
        success=True,
        message="背景图片上传成功",
        url=url,
    )


@router.post("/model", response_model=ModelUploadOut, summary="上传 Live2D 模型包")
async def upload_model(
    model_zip: UploadFile = File(..., description="模型压缩包 (.zip / .7z / .rar)"),
    user: User = Depends(get_current_user),
    _rate: None = Depends(check_upload_rate_limit),
) -> ModelUploadOut:
    """上传 Live2D 模型压缩包。

    仅接受 .zip / .7z / .rar 格式，最大 100 MB。
    后端接收后返回模型 ID，前端随后加载此模型。
    """
    if not model_zip.filename:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="未选择文件",
        )

    # 验证扩展名
    ext = os.path.splitext(model_zip.filename)[1].lower()
    content_type = model_zip.content_type or ""

    if ext not in ALLOWED_MODEL_EXTENSIONS and content_type not in ALLOWED_MODEL_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的压缩格式。仅接受 .zip / .7z / .rar。收到: {ext or content_type}",
        )

    # 验证文件大小
    contents = await model_zip.read()
    if len(contents) > MAX_MODEL_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"模型包过大。最大允许 100 MB，收到 {len(contents) / 1024 / 1024:.1f} MB",
        )

    # Validate magic number — .zip files must have PK header (§5.5)
    # .7z / .rar pass through (no magic bytes in table, validate_magic returns True)
    from app.core.file_validation import validate_magic
    if ext == ".zip" and not validate_magic(contents, "application/zip"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="文件不是有效的 zip 格式",
        )

    # Upload to OSS
    from app.infra.oss import get_oss_client

    oss_bucket = "eira-user-assets"
    model_id = f"user-{user.id}-{uuid.uuid4().hex[:12]}"
    oss_key = f"models/{user.id}/{model_id}{ext}"
    oss = get_oss_client()
    oss.put_object(
        Bucket=oss_bucket,
        Key=oss_key,
        Body=contents,
        ContentType=content_type or "application/octet-stream",
    )

    return ModelUploadOut(
        success=True,
        message="模型包上传成功，解析完成",
        model_id=model_id,
    )
