"""Admin user management endpoints — list, view, modify role/disabled status, soft-delete."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from app.core.deps import get_identity_service, require_admin, check_write_rate_limit
from app.domain.identity.service import IdentityService
from app.domain.identity.schemas import UserOut, UserDetailOut, PaginatedUsers, UserPatchIn
from app.domain.identity.models import User

router = APIRouter(prefix="/admin/users", tags=["admin-users"])


@router.get("", response_model=PaginatedUsers, summary="列出所有用户")
async def list_users(
    keyword: str | None = Query(None, description="搜索关键词（邮箱/昵称）"),
    role: str | None = Query(None, description="按角色筛选"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _admin: User = Depends(require_admin),
    svc: IdentityService = Depends(get_identity_service),
) -> PaginatedUsers:
    """分页列出所有未删除用户，支持关键词搜索和角色筛选。"""
    return await svc.list_users(keyword=keyword, role=role, page=page, page_size=page_size)


@router.get("/{uid}", response_model=UserDetailOut, summary="获取用户详情")
async def get_user(
    uid: int,
    _admin: User = Depends(require_admin),
    svc: IdentityService = Depends(get_identity_service),
) -> UserDetailOut:
    """获取单个用户的详细信息（含状态/禁用标记/时间戳）。"""
    return await svc.get_user_detail(uid)


@router.patch("/{uid}", response_model=UserOut, summary="修改用户角色或禁用状态")
async def patch_user(
    uid: int,
    body: UserPatchIn,
    admin: User = Depends(require_admin),
    svc: IdentityService = Depends(get_identity_service),
    _rate: None = Depends(check_write_rate_limit),
) -> UserOut:
    """修改用户角色或禁用状态。

    安全防护：
    - 管理员不能修改自己的角色或禁用自己
    - 不能禁用/降级最后一个活跃管理员
    """
    u = None
    if body.role is not None:
        u = await svc.set_user_role(uid, body.role, admin.id)
    if body.disabled is not None:
        u = await svc.set_user_disabled(uid, body.disabled, admin.id)
    if u is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "no_fields_to_update")
    return UserOut(id=u.id, email=u.email, display_name=u.display_name, role=u.role)


@router.delete("/{uid}", status_code=status.HTTP_204_NO_CONTENT, summary="软删除用户")
async def delete_user(
    uid: int,
    admin: User = Depends(require_admin),
    svc: IdentityService = Depends(get_identity_service),
    _rate: None = Depends(check_write_rate_limit),
) -> None:
    """软删除用户（设置 deleted_at 时间戳）。

    安全防护：
    - 管理员不能删除自己
    - 不能删除最后一个活跃管理员
    """
    await svc.soft_delete_user(uid, admin.id)
