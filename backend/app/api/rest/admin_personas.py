"""Admin persona management endpoints — full CRUD across all personas."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db_session, require_admin, check_write_rate_limit
from app.domain.identity.models import User
from app.domain.persona.repository import PersonaRepository
from app.domain.persona.service import PersonaService
from app.domain.persona.schemas import PersonaCreateIn, PersonaPatchIn, PersonaOut, PersonaListOut


class ImportIn(BaseModel):
    """SillyTavern V2 JSON import payload."""
    data: dict
    scope: str = "public"


def get_persona_service(db: AsyncSession = Depends(get_db_session)) -> PersonaService:
    return PersonaService(PersonaRepository(db))


router = APIRouter(prefix="/admin/personas", tags=["admin-personas"])


@router.get("", response_model=PersonaListOut, summary="列出所有角色卡")
async def list_personas(
    scope: str | None = Query(None, description="按 scope 筛选: public / user"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _admin: User = Depends(require_admin),
    svc: PersonaService = Depends(get_persona_service),
) -> PersonaListOut:
    """管理端：列出系统中所有角色卡，含已禁用的。"""
    return await svc.list_personas_admin(scope=scope, page=page, page_size=page_size)


@router.get("/{persona_id}", response_model=PersonaOut, summary="获取角色卡详情")
async def get_persona(
    persona_id: int,
    _admin: User = Depends(require_admin),
    svc: PersonaService = Depends(get_persona_service),
) -> PersonaOut:
    """管理端：获取单个角色卡详情。"""
    p = await svc.get_persona(persona_id)
    from app.domain.persona.service import _to_out
    return _to_out(p)


@router.post("", status_code=status.HTTP_201_CREATED, response_model=PersonaOut, summary="创建角色卡")
async def create_persona(
    body: PersonaCreateIn,
    _admin: User = Depends(require_admin),
    svc: PersonaService = Depends(get_persona_service),
    _rate: None = Depends(check_write_rate_limit),
) -> PersonaOut:
    """管理端：创建角色卡。"""
    return await svc.create_persona_admin(body)


@router.patch("/{persona_id}", response_model=PersonaOut, summary="更新角色卡")
async def patch_persona(
    persona_id: int,
    body: PersonaPatchIn,
    _admin: User = Depends(require_admin),
    svc: PersonaService = Depends(get_persona_service),
    _rate: None = Depends(check_write_rate_limit),
) -> PersonaOut:
    """管理端：部分更新角色卡。"""
    return await svc.patch_persona(persona_id, body, user_id=None)


@router.delete("/{persona_id}", status_code=status.HTTP_204_NO_CONTENT, summary="软删除角色卡")
async def delete_persona(
    persona_id: int,
    _admin: User = Depends(require_admin),
    svc: PersonaService = Depends(get_persona_service),
    _rate: None = Depends(check_write_rate_limit),
) -> None:
    """管理端：永久删除角色卡。"""
    await svc.delete_persona(persona_id)


@router.post("/{persona_id}/set-default", response_model=PersonaOut, summary="设为默认角色卡")
async def set_default_persona(
    persona_id: int,
    _admin: User = Depends(require_admin),
    svc: PersonaService = Depends(get_persona_service),
    _rate: None = Depends(check_write_rate_limit),
) -> PersonaOut:
    """管理端：将指定角色卡设为默认。"""
    return await svc.set_default(persona_id)


@router.post("/import", status_code=status.HTTP_201_CREATED, response_model=PersonaOut, summary="导入 SillyTavern V2 JSON")
async def import_persona_admin(
    body: ImportIn,
    _admin: User = Depends(require_admin),
    svc: PersonaService = Depends(get_persona_service),
    _rate: None = Depends(check_write_rate_limit),
) -> PersonaOut:
    """管理端：导入 SillyTavern V2 格式的角色卡 JSON。"""
    return await svc.import_v2(body.data, _admin.id, body.scope)
