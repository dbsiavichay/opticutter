"""
Importa todos los modelos aquí para que Alembic pueda detectarlos automáticamente.
Cuando crees modelos nuevos, impórtalos aquí para que las migraciones funcionen.

Ejemplo:
from .user import User
from .project import Project
"""


from typing import Optional

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from src.db import Base


class ClientModel(Base):
    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    phone: Mapped[str] = mapped_column(String(32), unique=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(64))
    last_name: Mapped[Optional[str]] = mapped_column(String(64))
