from typing import Optional

from sqlalchemy import Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.database.base import Base


class BoardModel(Base):
    """Modelo ORM para tableros/placas"""

    __tablename__ = "boards"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(128), unique=True)
    description: Mapped[Optional[str]] = mapped_column(String(256))
    length: Mapped[int] = mapped_column(Integer)
    width: Mapped[int] = mapped_column(Integer)
    thickness: Mapped[int] = mapped_column(Integer)
    grain_direction: Mapped[Optional[str]] = mapped_column(String(4))
    price: Mapped[float] = mapped_column(Float)
