"""Service d'authentification."""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash, verify_password
from app.models.user import User
from app.schemas.auth import UserCreate


async def get_user_by_username(session: AsyncSession, username: str) -> User | None:
    stmt = select(User).where(User.username == username)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def authenticate_user(session: AsyncSession, username: str, password: str) -> User | None:
    user = await get_user_by_username(session, username)
    if not user or not user.is_active:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


async def create_user(session: AsyncSession, user_in: UserCreate) -> User:
    hashed = get_password_hash(user_in.password)
    user = User(
        username=user_in.username,
        email=user_in.email,
        hashed_password=hashed,
        is_active=True,
        is_admin=user_in.is_admin,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user
