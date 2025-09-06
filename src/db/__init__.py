from sqlalchemy.orm import DeclarativeBase

"""
Configuración de base de datos con SQLAlchemy
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config import config


class Base(DeclarativeBase):
    pass


# Crear el engine de base de datos
engine = create_engine(
    config.DATABASE_URL,
    connect_args={"check_same_thread": False},  # Solo necesario para SQLite
)

# Crear la clase session
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """
    Dependencia para obtener la sesión de base de datos en FastAPI
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
