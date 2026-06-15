"""User-facing persona endpoints — list public/mine, CRUD own personas, import/export."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db_session, get_current_user, check_write_rate_limit
from app.domain.identity.models import User
from app.domain.persona.repository import PersonaRepository
from app.domain.persona.service import PersonaService
from app.domain.persona.schemas import PersonaCreateIn, PersonaPatchIn, PersonaOut, PersonaListOut


def get_persona_service(db: AsyncSession = Depends(get_db_session)) -> PersonaService:
    return PersonaService(PersonaRepository(db))


router = APIRouter(prefix="/personas", tags=["personas"])


class ImportIn(BaseModel):
    """SillyTavern V2 JSON import payload."""
    data: dict
    scope: str = "user"


# ── List ─────────────────────────────────────────────────────────────────


@router.get("", response_model=PersonaListOut, summary="列出可用角色卡")
async def list_personas(
    scope: str | None = Query(None, description="public / mine"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    svc: PersonaService = Depends(get_persona_service),
) -> PersonaListOut:
    """用户端：列出可见的角色卡（public + 自己创建的 user-scoped）。"""
    filter_scope = None if scope == "mine" else scope
    return await svc.list_personas_user(user_id=user.id, scope=filter_scope, page=page, page_size=page_size)


# ── Detail ───────────────────────────────────────────────────────────────


@router.get("/{persona_id}", response_model=PersonaOut, summary="获取角色卡详情")
async def get_persona(
    persona_id: int,
    user: User = Depends(get_current_user),
    svc: PersonaService = Depends(get_persona_service),
) -> PersonaOut:
    """用户端：查看角色卡详情（仅可查看 public 或自己创建的）。"""
    p = await svc.get_persona(persona_id)
    if p.scope == "user" and p.user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not_your_persona")
    from app.domain.persona.service import _to_out
    return _to_out(p)


# ── Create ───────────────────────────────────────────────────────────────


@router.post("", status_code=status.HTTP_201_CREATED, response_model=PersonaOut, summary="创建角色卡")
async def create_persona(
    body: PersonaCreateIn,
    user: User = Depends(get_current_user),
    svc: PersonaService = Depends(get_persona_service),
    _rate: None = Depends(check_write_rate_limit),
) -> PersonaOut:
    """用户端：创建角色卡。普通用户只能创建 user-scoped persona。"""
    if body.scope == "public" and user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "only_admin_can_create_public")
    return await svc.create_persona(body, user.id)


# ── Update ───────────────────────────────────────────────────────────────


@router.patch("/{persona_id}", response_model=PersonaOut, summary="更新角色卡")
async def patch_persona(
    persona_id: int,
    body: PersonaPatchIn,
    user: User = Depends(get_current_user),
    svc: PersonaService = Depends(get_persona_service),
    _rate: None = Depends(check_write_rate_limit),
) -> PersonaOut:
    """用户端：更新自己的角色卡。Admin 可更新任意。"""
    # Remove scope and disabled from user updates (admins use /admin/personas)
    if user.role != "admin":
        body.scope = None
        body.disabled = None
    return await svc.patch_persona(persona_id, body, user_id=user.id)


# ── Delete ───────────────────────────────────────────────────────────────


@router.delete("/{persona_id}", status_code=status.HTTP_204_NO_CONTENT, summary="删除角色卡")
async def delete_persona(
    persona_id: int,
    user: User = Depends(get_current_user),
    svc: PersonaService = Depends(get_persona_service),
    _rate: None = Depends(check_write_rate_limit),
) -> None:
    """用户端：软删除自己的角色卡。"""
    p = await svc.get_persona(persona_id)
    if p.scope == "user" and p.user_id != user.id and user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not_your_persona")
    await svc.delete_persona(persona_id)


# ── Import / Export ──────────────────────────────────────────────────────


@router.post("/import", status_code=status.HTTP_201_CREATED, response_model=PersonaOut, summary="导入 SillyTavern V2 JSON")
async def import_persona(
    body: ImportIn,
    user: User = Depends(get_current_user),
    svc: PersonaService = Depends(get_persona_service),
    _rate: None = Depends(check_write_rate_limit),
) -> PersonaOut:
    """导入 SillyTavern V2 格式的角色卡 JSON。"""
    if body.scope == "public" and user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "only_admin_can_create_public")
    return await svc.import_v2(body.data, user.id, body.scope)


@router.get("/{persona_id}/export", response_model=dict, summary="导出为 SillyTavern V2 JSON")
async def export_persona(
    persona_id: int,
    user: User = Depends(get_current_user),
    svc: PersonaService = Depends(get_persona_service),
) -> dict:
    """导出角色卡为 SillyTavern V2 兼容的 JSON 格式。"""
    p = await svc.get_persona(persona_id)
    if p.scope == "user" and p.user_id != user.id and user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not_your_persona")
    return svc.export_v2(p)
