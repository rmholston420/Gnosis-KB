"""Auth router — token issue, user registration, me endpoint.

Rate limits applied:
  POST /token    — 10/minute per IP  (brute-force protection)
  POST /register — 10/minute per IP  (registration spam protection)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gnosis.core.auth import (
    TokenData,
    create_access_token,
    get_password_hash,
    require_user,
    verify_password,
)
from gnosis.core.rate_limit import auth_limit, limiter
from gnosis.database import get_db
from gnosis.models.user import User
from gnosis.schemas.auth import Token, UserCreate, UserRead

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/token", response_model=Token, summary="Issue JWT token")
@auth_limit
async def login(
    request: Request,
    response: Response,
    form: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
) -> Token:
    """Exchange username+password for a bearer JWT."""
    result = await db.execute(select(User).where(User.email == form.username))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(form.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect credentials")
    token = create_access_token(TokenData(user_id=user.id, email=user.email))
    return Token(access_token=token)


@router.post("/register", response_model=UserRead, status_code=201, summary="Register a new user")
@auth_limit
async def register(
    request: Request,
    response: Response,
    payload: UserCreate,
    db: AsyncSession = Depends(get_db),
) -> User:
    """Create a new user account."""
    result = await db.execute(select(User).where(User.email == payload.email))
    if result.scalar_one_or_none() is not None:
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(
        email=payload.email,
        hashed_password=get_password_hash(payload.password),
        full_name=payload.full_name,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.get("/me", response_model=UserRead, summary="Get current authenticated user")
async def me(current: User = Depends(require_user)) -> User:
    """Return the currently authenticated user record."""
    return current
