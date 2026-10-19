"""Modèles SQLAlchemy (tables métier) de SM-Park.

Expose la base déclarative et les modèles afin de garantir que toutes les
tables sont enregistrées dans `Base.metadata` (création au démarrage).
"""
from app.models.allowed_plate import AllowedPlate
from app.models.barrier_command import BarrierCommand
from app.models.base import Base
from app.models.parking_slot import ParkingSlot
from app.models.passage import Passage
from app.models.user import User
from app.models.visit import Visit

__all__ = [
    "Base",
    "User",
    "AllowedPlate",
    "Passage",
    "ParkingSlot",
    "Visit",
    "BarrierCommand",
]
