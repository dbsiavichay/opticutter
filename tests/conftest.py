"""Fixtures compartidas: app con una base de datos SQLite aislada por test."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from main import app
from src.shared.database import Base, get_db

# Importar los modelos puebla ``Base.metadata`` antes de ``create_all``.
import src.modules.boards.model  # noqa: F401,E402
import src.modules.clients.model  # noqa: F401,E402
import src.modules.optimizations.model  # noqa: F401,E402


@pytest.fixture
def db_session():
    """Sesión sobre una base SQLite en memoria, recreada en cada test."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture
def client(db_session):
    """TestClient con ``get_db`` apuntando a la base aislada del test."""

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
