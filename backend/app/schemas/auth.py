"""Schémas Pydantic pour l'authentification."""
from pydantic import BaseModel


class UserCreate(BaseModel):
    """Création d'utilisateur PUBLIC (register).

    Ne contient volontairement PAS de champ `is_admin` : un dépôt public
    avec `"is_admin": true` ne doit jamais pouvoir s'auto-promouvoir.
    Les administrateurs sont créés par `POST /api/auth/admin/users`
    (protégé par `get_current_admin`) ou à l'initialisation de la base.
    """

    username: str
    password: str
    email: str | None = None


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
