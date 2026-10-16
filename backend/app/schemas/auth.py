"""Schémas Pydantic pour l'authentification."""
from pydantic import BaseModel


class UserCreate(BaseModel):
    username: str
    password: str
    email: str | None = None
    is_admin: bool = False


class UserRead(BaseModel):
    username: str
    email: str | None
    is_active: bool
    is_admin: bool

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: str | None = None
