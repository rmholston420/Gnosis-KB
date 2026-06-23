"""Pydantic schemas for auth endpoints."""

from pydantic import BaseModel, EmailStr


class Token(BaseModel):
    """JWT bearer token response."""

    access_token: str
    token_type: str = "bearer"


class UserCreate(BaseModel):
    """Payload to register a new user."""

    email: EmailStr
    password: str
    full_name: str = ""


class UserRead(BaseModel):
    """Safe user representation (no hashed_password)."""

    id: int
    email: str
    full_name: str | None
    is_active: bool
    is_superuser: bool

    model_config = {"from_attributes": True}
