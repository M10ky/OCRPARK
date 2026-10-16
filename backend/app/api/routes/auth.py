"""Routes d'authentification."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin, get_current_user
from app.core.security import create_access_token
from app.db.session import get_session
from app.models.user import User
from app.schemas.auth import Token, UserCreate, UserRead
from app.services.auth_service import authenticate_user, create_user, get_user_by_username

router = APIRouter(prefix="/api/auth", tags=["auth"])


async def _ensure_username_free(session: AsyncSession, username: str) -> None:
    existing = await get_user_by_username(session, username)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Nom d'utilisateur déjà utilisé",
        )


@router.post("/register", response_model=UserRead)
async def register(
    user_in: UserCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> UserRead:
    """Inscription publique : crée TOUJOURS un utilisateur non administrateur
    (le champ `is_admin`, s'il est envoyé, est ignoré par le schéma)."""
    await _ensure_username_free(session, user_in.username)
    try:
        user = await create_user(session, user_in, is_admin=False)
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Utilisateur déjà existant",
        ) from exc
    return UserRead.model_validate(user)


@router.post("/admin/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_admin_user(
    user_in: UserCreate,
    current_admin: Annotated[User, Depends(get_current_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> UserRead:
    """Crée un compte administrateur. Réservé aux administrateurs existants
    (amorçage : voir `ADMIN_INITIAL_PASSWORD` à l'initialisation de la base)."""
    await _ensure_username_free(session, user_in.username)
    try:
        user = await create_user(session, user_in, is_admin=True)
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Utilisateur déjà existant",
        ) from exc
    return UserRead.model_validate(user)


@router.post("/login", response_model=Token)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Token:
    user = await authenticate_user(session, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identifiants incorrects",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token(subject=user.username)
    return Token(access_token=token, token_type="bearer")


@router.get("/me", response_model=UserRead)
async def me(current_user: Annotated[User, Depends(get_current_user)]) -> UserRead:
    return UserRead.model_validate(current_user)
