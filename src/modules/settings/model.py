from sqlalchemy import JSON, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.database import Base
from src.shared.mixins import AuditMixin, TimestampMixin

# Configuration is unique: a single row with this fixed id (singleton pattern).
SETTINGS_ID = 1


class SettingsModel(TimestampMixin, AuditMixin, Base):
    """Application's single configuration (singleton row, ``id=1``).

    Persists what used to live only in environment variables: the cutting
    parameters and company data (proforma letterhead). The row is lazily
    seeded from ``config`` on first read, so deployment is backward-compatible.
    This table is the runtime source of truth; ``config`` only supplies the
    initial values.
    """

    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Cutting parameters (mm)
    kerf: Mapped[float] = mapped_column(Float)
    top_trim: Mapped[float] = mapped_column(Float)
    bottom_trim: Mapped[float] = mapped_column(Float)
    left_trim: Mapped[float] = mapped_column(Float)
    right_trim: Mapped[float] = mapped_column(Float)
    edge_banding_waste_factor: Mapped[float] = mapped_column(Float)
    half_board_markup_pct: Mapped[float] = mapped_column(Float)

    # Pre-orders (mutable quote): validity period and open-orders cap per client
    preorder_validity_days: Mapped[int] = mapped_column(Integer)
    max_open_preorders_per_client: Mapped[int] = mapped_column(Integer)

    # Price tiers: list of rates {code, name, rate, is_active, sort_order}.
    # The discount (rate) is applied to the base price of catalog boards.
    # Nullable/legacy is tolerated by falling back to config.PRICE_TIERS.
    price_tiers: Mapped[list] = mapped_column(JSON, default=list)

    # Company data (proforma letterhead)
    company_name: Mapped[str] = mapped_column(String(128))
    company_tagline: Mapped[str] = mapped_column(String(256))
    company_email: Mapped[str] = mapped_column(String(128))
    company_phone: Mapped[str] = mapped_column(String(128))
    company_branches: Mapped[list] = mapped_column(JSON, default=list)
