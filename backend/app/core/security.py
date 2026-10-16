"""Sécurité (hachage mots de passe + tokens JWT)."""
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from jose import JWTError, jwt

from app.core.config import get_settings

settings = get_settings()


def _truncate(pw: str) -> bytes:
    return pw.encode("utf-8")[:72] if pw else b""


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(_truncate(plain_password), hashed_password.encode("utf-8") if isinstance(hashed_password, str) else hashed_password)
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(_truncate(password), bcrypt.gensalt()).decode("utf-8")


def create_access_token(subject: str, expires_delta: timedelta | None = None) -> str:
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode: dict[str, Any] = {"sub": subject, "exp": expire}
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        sub = payload.get("sub")
        return str(sub) if sub is not None else None
    except JWTError:
        return None
