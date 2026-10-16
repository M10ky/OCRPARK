"""Modèles SQLAlchemy (tables métier) de SM-Park.

Expose la base déclarative et les modèles afin de garantir que toutes les
tables sont enregistrées dans `Base.metadata` (création au démarrage).
"""
from app.models.allowed_plate import AllowedPlate
from app.models.base import Base
from app.models.passage import Passage
from app.models.user import User

__all__ = ["Base", "User", "AllowedPlate", "Passage"]
