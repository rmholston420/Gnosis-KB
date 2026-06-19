"""JWT authentication core — single-user bcrypt + HS256 token.

Pattern adapted from fastapi/full-stack-fastapi-template (MIT).
No external OAuth required; the single owner is configured via
INITIAL_ADMIN_EMAIL + INITIAL_ADMIN_PASSWORD env vars.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from gnosis.config import settings
from gnosis.database import get_db
from gnosis.models.user import User
from sqlalchemy import select

ALGORITHM = "HS256"
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token", auto_error=False)


class TokenData(BaseModel):
    """Payload embedded inside the JWT."""

    user_id: int
    email: str


def verify_password(plain: str, hashed: str) -> bool:
    """Return True if plain password matches the stored bcrypt hash."""
    return pwd_context.verify(plain, hashed)


def get_password_hash(plain: str) -> str:
    """Return a bcrypt hash for *plain*."""
    return pwd_context.hash(plain)


def create_access_token(data: TokenData, expires_delta: Optional[timedelta] = None) -> str:
    """Encode *data* into a signed JWT with configurable expiry."""
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    payload = {"sub": str(data.user_id), "email": data.email, "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """Decode JWT and return the corresponding User row, or None if unauthenticated.

    When AUTH_REQUIRED=false (default) this returns a synthetic admin user so
    the app works without a login screen for single-user local use.
    """
    if not settings.auth_required:
        # Auto-authenticate as the bootstrap admin
        result = await db.execute(select(User).where(User.is_active == True).limit(1))  # noqa: E712
        user = result.scalar_one_or_none()
        return user

    if token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        user_id: int = int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    result = await db.execute(select(User).where(User.id == user_id, User.is_active == True))  # noqa: E712
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


async def require_user(current: Optional[User] = Depends(get_current_user)) -> User:
    """Dependency that raises 401 when no user is resolved."""
    if current is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Login required")
    return current
