"""JWT authentication core — bcrypt + HS256 tokens + vault-scoped request dependency.

Pattern adapted from fastapi/full-stack-fastapi-template (MIT).
No external OAuth required; the owner is configured via
INITIAL_ADMIN_EMAIL + INITIAL_ADMIN_PASSWORD env vars.

Dependency hierarchy
--------------------
    oauth2_scheme                     (FastAPI security scheme)
        └─ get_current_user           Optional[User] — None only when auth_required=False
                └─ require_user       User            — raises 401 when no user resolved
                └─ get_vault_owner_ids -> set[int]   — honours X-Vault-Owner-Id header

Vault scoping
-------------
Every router that reads notes should declare::

    owner_ids: set[int] = Depends(get_vault_owner_ids)

This replaces any ad-hoc call to ``get_accessible_owner_ids()`` in the
router body.  The dependency:

1. Resolves ``current_user`` via JWT / auto-auth.
2. Reads the optional ``X-Vault-Owner-Id`` request header (sent by the
   frontend VaultSwitcher when browsing a shared vault).
3. If the header is absent → returns all owner IDs the caller may access
   (own vault + accepted grants).
4. If the header is present → validates the caller has an active grant for
   that specific owner ID, then returns ``{target_id}`` so the query is
   scoped exclusively to the requested vault.
5. Invalid header value → HTTP 400.  No grant → HTTP 403.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gnosis.config import settings
from gnosis.database import get_db
from gnosis.models.user import User

ALGORITHM = "HS256"
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token", auto_error=False)

_VAULT_HEADER = "X-Vault-Owner-Id"


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


def create_access_token(data: TokenData, expires_delta: timedelta | None = None) -> str:
    """Encode *data* into a signed JWT with configurable expiry."""
    expire = datetime.now(UTC) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    payload = {"sub": str(data.user_id), "email": data.email, "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


async def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """Decode JWT and return the corresponding User row, or None if unauthenticated.

    When AUTH_REQUIRED=false (default) this returns a synthetic admin user so
    the app works without a login screen for single-user local use.
    """
    if not settings.auth_required:
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

    result = await db.execute(
        select(User).where(User.id == user_id, User.is_active == True)  # noqa: E712
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


async def require_user(current: User | None = Depends(get_current_user)) -> User:
    """Dependency that raises 401 when no user is resolved."""
    if current is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Login required")
    return current


async def get_vault_owner_ids(
    request: Request,
    current_user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
) -> set[int]:
    """FastAPI dependency: resolve the set of owner IDs for this request.

    Reads the optional ``X-Vault-Owner-Id`` header injected by the frontend
    VaultSwitcher.  Behaviour:

    * **Header absent** — returns ``get_accessible_owner_ids(current_user)``
      (own vault + every vault the user has an accepted grant for).

    * **Header present, valid int, caller has grant** — returns
      ``{target_id}`` so the entire request is scoped to only that vault.

    * **Header present, valid int, caller has NO grant** — raises HTTP 403
      Forbidden.  No note data is returned.

    * **Header present but not a valid int** — raises HTTP 400 Bad Request.

    Usage in a router::

        @router.get("/notes/")
        async def list_notes(
            db: AsyncSession = Depends(get_db),
            owner_ids: set[int] = Depends(get_vault_owner_ids),
        ):
            stmt = scoped_note_stmt(select(Note), owner_ids)
            ...
    """
    # Local import to avoid circular dependency at module load time
    # (namespace imports models; auth imports nothing from gnosis.routers)
    from gnosis.core.namespace import get_accessible_owner_ids

    raw_header = request.headers.get(_VAULT_HEADER)

    if raw_header is None:
        # No targeting header — return all accessible vaults
        return await get_accessible_owner_ids(current_user, db)

    # Parse the header value
    try:
        target_id = int(raw_header)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid {_VAULT_HEADER} header value: {raw_header!r}. Must be an integer user ID.",
        )

    # If the caller is requesting their own vault explicitly, short-circuit
    if target_id == current_user.id:
        return {current_user.id}

    # Verify the caller has an active grant for the requested vault
    try:
        await get_accessible_owner_ids(current_user, db, target_owner_id=target_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"You do not have an active grant to access the vault owned by user {target_id}. "
                "Ask the vault owner to invite you via Settings → Vault Sharing."
            ),
        )

    # Scope exclusively to the requested vault
    return {target_id}
