from datetime import datetime, timedelta, timezone
from typing import Literal
from jose import jwt, JWTError
from passlib.context import CryptContext
from app.core.config import get_settings

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)


def hash_password(p: str) -> str:
    return _pwd.hash(p)


def verify_password(p: str, h: str) -> bool:
    return _pwd.verify(p, h)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def issue_token(sub: str, role: str, kind: Literal["access", "refresh"]) -> str:
    s = get_settings().jwt
    ttl = s.access_ttl_seconds if kind == "access" else s.refresh_ttl_seconds
    payload = {
        "sub": sub,
        "role": role,
        "kind": kind,
        "iat": int(_now().timestamp()),
        "exp": int((_now() + timedelta(seconds=ttl)).timestamp()),
    }
    return jwt.encode(payload, s.secret, algorithm=s.algorithm)


def decode_token(token: str) -> dict:
    s = get_settings().jwt
    try:
        return jwt.decode(token, s.secret, algorithms=[s.algorithm])
    except JWTError as e:
        raise ValueError("invalid_token") from e
