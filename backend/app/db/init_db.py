"""Initialisation de la base (places de parking + admin dev si nécessaire).

Sécurité : aucun mot de passe n'est codé en dur. L'administrateur initial n'est
créé que si `ADMIN_INITIAL_PASSWORD` est défini ET différent de la valeur faible
`admin`. Le mot de passe n'est JAMAIS journalisé.
"""
import asyncio
import logging
import os

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import get_password_hash
from app.db.session import AsyncSessionLocal
from app.models.parking_slot import ParkingSlot
from app.models.user import User

logger = logging.getLogger("smpark.init_db")


async def seed_parking_slots(session) -> None:
    """Crée les places manquantes 1..PARKING_SLOT_COUNT (idempotent)."""
    total = max(0, get_settings().PARKING_SLOT_COUNT)
    result = await session.execute(select(ParkingSlot.id))
    present = set(result.scalars().all())

    created = 0
    for slot_id in range(1, total + 1):
        if slot_id not in present:
            session.add(ParkingSlot(id=slot_id, occupied=False))
            created += 1
    if created:
        await session.commit()
        logger.info(
            "[init_db] %d place(s) de parking initialisée(s) (total=%d).",
            created,
            total,
        )


async def _ensure_initial_admin(session) -> None:
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


async def init_db() -> None:
    async with AsyncSessionLocal() as session:
        await seed_parking_slots(session)
        await _ensure_initial_admin(session)


if __name__ == "__main__":
    asyncio.run(init_db())
