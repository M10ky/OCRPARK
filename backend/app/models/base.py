"""Classe de base déclarative pour tous les modèles SQLAlchemy."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base commune : centralise les métadonnées des tables."""
