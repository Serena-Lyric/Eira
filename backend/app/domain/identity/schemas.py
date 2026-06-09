from pydantic import BaseModel, EmailStr, Field


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str | None = None


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: int
    email: str
    display_name: str | None = None
    role: str


class UserDetailOut(UserOut):
    status: str
    disabled: bool = False
    created_at: str | None = None
    updated_at: str | None = None


class PaginatedUsers(BaseModel):
    items: list[UserOut]
    total: int
    page: int
    page_size: int


class UserPatchIn(BaseModel):
    role: str | None = None
    disabled: bool | None = None
