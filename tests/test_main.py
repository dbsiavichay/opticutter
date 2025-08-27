from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


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
