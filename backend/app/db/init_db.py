"""Initialisation de la base (création admin dev si nécessaire)."""
import asyncio
import os

from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import get_password_hash
from app.db.session import AsyncSessionLocal
from app.models.user import User


async def init_db() -> None:
    async with AsyncSessionLocal() as session:
        stmt = select(User).where(User.username == "admin")
        res = await session.execute(stmt)
        if res.scalar_one_or_none() is None:
            pwd = os.getenv("ADMIN_INITIAL_PASSWORD") or "admin"
            user = User(
                username="admin",
                hashed_password=get_password_hash(pwd),
                is_active=True,
                is_admin=True,
            )
            session.add(user)
            await session.commit()
            print(f"[init_db] Admin créé (username=admin)")


if __name__ == "__main__":
    asyncio.run(init_db())
