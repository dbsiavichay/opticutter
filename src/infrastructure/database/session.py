from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.core.config import config

engine = create_engine(
    config.DATABASE_URL,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """Dependencia para obtener la sesión de base de datos en FastAPI"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
