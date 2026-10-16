"""Initialisation de la base (création admin dev si nécessaire).

Sécurité : aucun mot de passe n'est codé en dur. L'administrateur initial n'est
créé que si `ADMIN_INITIAL_PASSWORD` est défini ET différent de la valeur faible
`admin`. Le mot de passe n'est JAMAIS journalisé.
"""
import asyncio
import logging
import os

from sqlalchemy import select

from app.core.security import get_password_hash
from app.db.session import AsyncSessionLocal
from app.models.user import User

logger = logging.getLogger("smpark.init_db")


async def init_db() -> None:
    async with AsyncSessionLocal() as session:
        stmt = select(User).where(User.username == "admin")
        res = await session.execute(stmt)
        if res.scalar_one_or_none() is not None:
            return

        pwd = (os.getenv("ADMIN_INITIAL_PASSWORD") or "").strip()
        if not pwd or pwd == "admin":
            logger.warning(
                "[init_db] Aucun administrateur créé : ADMIN_INITIAL_PASSWORD est "
                "absent ou vaut la valeur faible 'admin'. Définissez un mot de "
                "passe robuste dans .env puis relancez le backend (le mot de passe "
                "n'est jamais journalisé). En attendant, aucune route protégée "
                "par admin n'est utilisable."
            )
            return

        user = User(
            username="admin",
            hashed_password=get_password_hash(pwd),
            is_active=True,
            is_admin=True,
        )
        session.add(user)
        await session.commit()
        logger.info("[init_db] Compte administrateur créé (username=admin).")


if __name__ == "__main__":
    asyncio.run(init_db())
