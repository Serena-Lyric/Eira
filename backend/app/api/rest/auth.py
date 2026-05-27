from fastapi import APIRouter, Depends, status
from app.core.deps import get_identity_service, get_current_user
from app.domain.identity.service import IdentityService
from app.domain.identity.schemas import RegisterIn, LoginIn, TokenPair, UserOut
from app.domain.identity.models import User
from pydantic import BaseModel

router = APIRouter(prefix="/auth", tags=["auth"])


class RefreshIn(BaseModel):
    refresh_token: str


@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=UserOut)
async def register(
    p: RegisterIn, svc: IdentityService = Depends(get_identity_service)
):
    u = await svc.register(p)
    return UserOut(
        id=u.id, email=u.email, display_name=u.display_name, role=u.role
    )


@router.post("/login", response_model=TokenPair)
async def login(p: LoginIn, svc: IdentityService = Depends(get_identity_service)):
    return await svc.login(p)


@router.post("/refresh", response_model=TokenPair)
async def refresh(
    p: RefreshIn, svc: IdentityService = Depends(get_identity_service)
):
    return await svc.refresh(p.refresh_token)


@router.get("/me", response_model=UserOut)
async def me(u: User = Depends(get_current_user)):
    return UserOut(
        id=u.id, email=u.email, display_name=u.display_name, role=u.role
    )
