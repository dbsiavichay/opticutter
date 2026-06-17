"""Fixtures compartidas: app con una base de datos SQLite aislada por test."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Importar los modelos puebla ``Base.metadata`` antes de ``create_all``.
import src.modules.branches.model  # noqa: F401,E402
import src.modules.clients.model  # noqa: F401,E402
import src.modules.optimization_drafts.model  # noqa: F401,E402
import src.modules.optimizations.model  # noqa: F401,E402
import src.modules.orders.model  # noqa: F401,E402
import src.modules.preorders.model  # noqa: F401,E402
import src.modules.products.model  # noqa: F401,E402
import src.modules.settings.model  # noqa: F401,E402
import src.modules.users.model  # noqa: F401,E402
import src.modules.users.refresh_token_model  # noqa: F401,E402
from main import app
from src.modules.branches.model import BranchModel
from src.modules.users.schemas import UserCreate
from src.modules.users.service import UserService
from src.shared.cache import cache
from src.shared.database import Base, get_db

# Credenciales del admin que el cliente autenticado por defecto usa (ver ``client``).
_CONFTEST_ADMIN_EMAIL = "conftest-admin@empresa.com"
_CONFTEST_ADMIN_PWD = "conftest-admin-pwd"

# Sucursal por defecto sembrada en cada base de prueba (primer insert ⇒ id estable).
# Las suites la referencian al crear órdenes/pre-órdenes/borradores/usuarios staff.
DEFAULT_BRANCH_ID = 1


class _InMemoryRedis:
    """Doble en memoria de Redis: parea ``get``/``set`` sobre strings JSON."""

    def __init__(self):
        self._store: dict = {}

    def get(self, key):
        return self._store.get(key)

    def set(self, key, value, ex=None):
        self._store[key] = value
        return True


@pytest.fixture(autouse=True)
def isolated_cache():
    """Aísla la caché de Redis real: cada test usa un doble en memoria limpio."""
    original_client, original_initialized = cache._client, cache._initialized
    cache._client = _InMemoryRedis()
    cache._initialized = True
    try:
        yield
    finally:
        cache._client, cache._initialized = original_client, original_initialized


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
    # Siembra la sucursal por defecto (id=1): el aislamiento multi-sucursal exige
    # que órdenes/pre-órdenes/borradores y el staff cuelguen de una sucursal.
    session.add(BranchModel(code="MATRIZ", name="Casa Matriz", is_active=True))
    session.commit()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture
def anon_client(db_session):
    """TestClient sin autenticación, con ``get_db`` sobre la base aislada del test.

    Para los tests de auth (login, refresh, enforcement por rol), que controlan el
    header ``Authorization`` por request. El resto de suites usa ``client``.
    """

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def client(anon_client, db_session):
    """TestClient autenticado como administrador por defecto.

    El enforcement RBAC protege casi todos los endpoints; para que las suites de
    cada módulo prueben su lógica sin fricción de auth, este cliente adjunta por
    defecto el Bearer de un admin sembrado. Los tests que necesitan controlar la
    autenticación (``test_users.py``) usan ``anon_client``.
    """
    svc = UserService(db_session)
    if svc.get_by_email(_CONFTEST_ADMIN_EMAIL) is None:
        svc.create(
            UserCreate(
                email=_CONFTEST_ADMIN_EMAIL,
                password=_CONFTEST_ADMIN_PWD,
                role="administrador",
                full_name="Conftest Admin",
            )
        )
    resp = anon_client.post(
        "/api/v1/auth/login",
        json={"email": _CONFTEST_ADMIN_EMAIL, "password": _CONFTEST_ADMIN_PWD},
    )
    token = resp.json()["data"]["accessToken"]
    anon_client.headers.update({"Authorization": f"Bearer {token}"})
    return anon_client
