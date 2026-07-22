from sqlalchemy import Boolean, CheckConstraint, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.database import Base
from src.shared.mixins import AuditMixin, TimestampMixin


class AdditionalServiceModel(TimestampMixin, AuditMixin, Base):
    """Catalog of additional services billed on a quote on top of the cut materials.

    A service (perforación, armado, instalación de bisagras, …) is **not** cut
    geometry: it never feeds the optimizer. It carries a default ``price`` that a
    quote seeds and staff may override per line. ``is_active`` hides retired
    services from the quote picker without deleting their history.
    """

    __tablename__ = "additional_services"
    __table_args__ = (CheckConstraint("price >= 0", name="price_non_negative"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), unique=True)
    price: Mapped[float] = mapped_column(Float)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
