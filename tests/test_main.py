import os
import subprocess
import sys

from fastapi.testclient import TestClient

from main import app
from src.shared.database import get_db

client = TestClient(app)


def _product_payload(code="MEL18"):
    return {
        "type": "board",
        "code": code,
        "name": f"Melamina {code}",
        "price": 45.5,
        "attributes": {"height": 2440, "width": 1220, "thickness": 18},
    }


def test_app_mappers_configure_without_extra_model_imports():
    """Regresión: la app debe configurar los mappers de SQLAlchemy solo con los
    modelos que importa ``main`` (vía routers). No debe depender de que algo más
    importe ``optimizations.model``.

    Se corre en un subproceso aislado porque ``conftest`` importa TODOS los modelos
    y enmascararía el problema: el 500 ``failed to locate 'OptimizationModel'`` solo
    aparecía en el runtime real de la app (p. ej. ``GET /clients/identifier/...``).
    """
    code = (
        "import main; "
        "from sqlalchemy.orm import configure_mappers; "
        "configure_mappers()"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        env={**os.environ, "ENVIRONMENT": "local"},
    )
    assert result.returncode == 0, result.stderr


def test_root_redirect():
    """Test que la ruta raíz redirige a /docs"""
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/docs"


def test_health_check():
    """Test del endpoint de health check básico"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "environment" in data
    assert "version" in data


def test_api_health_check():
    """Test del endpoint de health check de la API"""
    response = client.get("/api/v1/health/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "environment" in data
    assert "version" in data


def test_readiness_check():
    """Test del endpoint de readiness check"""
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert "checks" in data


def test_cutter_info():
    """Test del endpoint de información de Cutter"""
    response = client.get("/api/v1/cutter/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "version" in data
    assert "features" in data
    assert isinstance(data["features"], list)


def test_cutter_status():
    """Test del endpoint de estado de Cutter"""
    response = client.get("/api/v1/cutter/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "operational"
    assert "active_processes" in data
    assert "last_update" in data


def test_success_response_has_meta_and_request_id_header(client):
    """Toda respuesta de éxito trae ``meta`` y ecoa el requestId en el header."""
    resp = client.post("/api/v1/products/", json=_product_payload())
    assert resp.status_code == 201
    body = resp.json()
    assert "data" in body
    meta = body["meta"]
    assert meta["requestId"]
    assert meta["timestamp"]
    assert resp.headers["x-request-id"] == meta["requestId"]


def test_incoming_request_id_is_propagated(client):
    """Un ``X-Request-ID`` entrante se conserva (continuidad de traza) y va en meta."""
    resp = client.get("/api/v1/products/999999", headers={"X-Request-ID": "trace-123"})
    assert resp.status_code == 404
    assert resp.headers["x-request-id"] == "trace-123"
    assert resp.json()["meta"]["requestId"] == "trace-123"


def test_validation_error_includes_field_path(client):
    """Validación de request → 422 con ``code`` y ``field`` tipo ``body.<campo>``."""
    # ``type`` válido (discriminador) con el resto de campos faltantes: el error
    # apunta a los subcampos del producto (``body.board.<campo>``).
    resp = client.post("/api/v1/products/", json={"type": "board"})
    assert resp.status_code == 422
    errors = resp.json()["errors"]
    assert errors[0]["code"] == "VALIDATION_ERROR"
    assert any(e["field"] and e["field"].startswith("body.") for e in errors)


def test_unknown_route_returns_404_envelope(client):
    """Una ruta inexistente también responde con la envoltura ``{errors, meta}``."""
    resp = client.get("/api/v1/nope")
    assert resp.status_code == 404
    body = resp.json()
    assert body["errors"][0]["code"] == "NOT_FOUND"
    assert body["meta"]["requestId"]


def test_unhandled_exception_returns_500_envelope(db_session, monkeypatch):
    """Una excepción no controlada se traduce a un 500 con envoltura, sin filtrar."""

    def _boom(self, id):
        raise RuntimeError("boom")

    from src.modules.products.service import ProductService

    monkeypatch.setattr(ProductService, "get_or_404", _boom)

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app, raise_server_exceptions=False) as test_client:
            resp = test_client.get("/api/v1/products/1")
        assert resp.status_code == 500
        body = resp.json()
        assert body["errors"][0]["code"] == "INTERNAL_SERVER_ERROR"
        assert body["errors"][0]["message"] == "Error interno del servidor"
        assert body["meta"]["requestId"]
    finally:
        app.dependency_overrides.clear()
