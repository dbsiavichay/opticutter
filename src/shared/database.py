from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from src.shared.config import config


class Base(DeclarativeBase):
    """Clase base para todos los modelos ORM."""


# ``check_same_thread`` solo aplica a SQLite; otros motores no lo aceptan.
_connect_args = (
    {"check_same_thread": False} if config.DATABASE_URL.startswith("sqlite") else {}
)

engine = create_engine(config.DATABASE_URL, connect_args=_connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """Dependencia FastAPI: provee una sesión de base de datos por request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
