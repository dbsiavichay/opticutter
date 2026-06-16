"""Tests del módulo users: helpers de seguridad, CRUD, login y dependencias."""

import pytest

from src.modules.users.dependencies import require_role
from src.modules.users.enums import UserRole
from src.modules.users.model import UserModel
from src.modules.users.permissions import RESOURCE_ROLES
from src.shared.exceptions import AuthenticationError, AuthorizationError
from src.shared.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def _user_payload(
    email="seller@empresa.com",
    password="supersecret",
    role="vendedor",
    full_name="Vendedor Uno",
):
    return {
        "email": email,
        "password": password,
        "role": role,
        "fullName": full_name,
    }


def _create_user(client, **kw):
    return client.post("/api/v1/users/", json=_user_payload(**kw))


def _login(client, email, password):
    return client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )


def _auth_header(token):
    return {"Authorization": f"Bearer {token}"}


# --- Helpers de seguridad (unitarios, sin DB) -------------------------------


def test_password_hash_round_trip():
    hashed = hash_password("supersecret")
    assert hashed != "supersecret"
    assert verify_password("supersecret", hashed) is True
    assert verify_password("wrong-password", hashed) is False


def test_verify_password_with_corrupt_hash_is_false():
    assert verify_password("whatever", "not-a-bcrypt-hash") is False


def test_jwt_round_trip_carries_claims():
    token = create_access_token(subject=42, role="administrador")
    payload = decode_access_token(token)
    assert payload["sub"] == "42"
    assert payload["role"] == "administrador"


def test_expired_token_raises_authentication_error():
    token = create_access_token(subject=1, role="vendedor", expires_minutes=-1)
    with pytest.raises(AuthenticationError):
        decode_access_token(token)


def test_tampered_token_raises_authentication_error():
    token = create_access_token(subject=1, role="vendedor")
    tampered = token[:-1] + ("a" if token[-1] != "a" else "b")
    with pytest.raises(AuthenticationError):
        decode_access_token(tampered)


# --- require_role (unitario) ------------------------------------------------


def _fake_user(role):
    return UserModel(
        id=1,
        email="x@y.com",
        hashed_password="x",
        role=role,
        is_active=True,
    )


def test_require_role_allows_matching_role():
    dep = require_role(UserRole.ADMIN, UserRole.SELLER)
    user = _fake_user("vendedor")
    assert dep(current_user=user) is user


def test_require_role_blocks_other_role():
    dep = require_role(UserRole.ADMIN)
    with pytest.raises(AuthorizationError):
        dep(current_user=_fake_user("operador"))


# --- CRUD vía API -----------------------------------------------------------


def test_create_user_hashes_password_and_hides_it(client):
    resp = _create_user(client)
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["email"] == "seller@empresa.com"
    assert data["role"] == "vendedor"
    assert data["isActive"] is True
    assert "id" in data
    # La contraseña ni su hash se exponen jamás.
    assert "password" not in data
    assert "hashedPassword" not in data


def test_create_user_role_is_case_insensitive(client):
    resp = _create_user(client, email="admin2@empresa.com", role="ADMINISTRADOR")
    assert resp.status_code == 201
    assert resp.json()["data"]["role"] == "administrador"


def test_create_duplicate_email_returns_409(client):
    _create_user(client)
    dup = _create_user(client, full_name="Otro")
    assert dup.status_code == 409
    assert dup.json()["errors"][0]["message"] == "El email ya está registrado"


def test_invalid_email_returns_422(client):
    resp = _create_user(client, email="no-es-email")
    assert resp.status_code == 422


def test_short_password_returns_422(client):
    resp = _create_user(client, password="short")
    assert resp.status_code == 422


def test_get_missing_user_returns_404(client):
    resp = client.get("/api/v1/users/999999")
    assert resp.status_code == 404
    assert resp.json()["errors"][0]["code"] == "NOT_FOUND"


def test_list_and_search_users(client):
    _create_user(client, email="ana@empresa.com", full_name="Ana")
    _create_user(client, email="beto@empresa.com", full_name="Beto")
    all_users = client.get("/api/v1/users/")
    assert all_users.status_code == 200
    assert all_users.json()["meta"]["pagination"]["total"] == 2
    found = client.get("/api/v1/users/", params={"search": "ana"})
    assert [u["email"] for u in found.json()["data"]] == ["ana@empresa.com"]


def test_update_user_fields(client):
    created = _create_user(client).json()["data"]
    resp = client.put(
        f"/api/v1/users/{created['id']}",
        json={"fullName": "Nuevo Nombre", "role": "operador"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["fullName"] == "Nuevo Nombre"
    assert data["role"] == "operador"


def test_update_password_allows_login_with_new_password(client):
    created = _create_user(client).json()["data"]
    client.put(f"/api/v1/users/{created['id']}", json={"password": "brand-new-pass"})
    # La contraseña vieja deja de servir; la nueva funciona.
    assert _login(client, "seller@empresa.com", "supersecret").status_code == 401
    assert _login(client, "seller@empresa.com", "brand-new-pass").status_code == 200


def test_delete_user(client):
    created = _create_user(client).json()["data"]
    assert client.delete(f"/api/v1/users/{created['id']}").status_code == 204
    assert client.get(f"/api/v1/users/{created['id']}").status_code == 404


# --- Login / auth -----------------------------------------------------------


def test_login_success_returns_token_and_user(client):
    _create_user(client)
    resp = _login(client, "seller@empresa.com", "supersecret")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["tokenType"] == "bearer"
    assert data["accessToken"]
    assert data["expiresIn"] > 0
    assert data["user"]["email"] == "seller@empresa.com"
    assert data["user"]["role"] == "vendedor"


def test_login_wrong_password_returns_401(client):
    _create_user(client)
    resp = _login(client, "seller@empresa.com", "incorrecta")
    assert resp.status_code == 401
    assert resp.json()["errors"][0]["code"] == "UNAUTHORIZED"


def test_login_unknown_email_returns_401(client):
    resp = _login(client, "nadie@empresa.com", "supersecret")
    assert resp.status_code == 401


def test_login_inactive_user_returns_401(client):
    created = _create_user(client).json()["data"]
    client.put(f"/api/v1/users/{created['id']}", json={"isActive": False})
    resp = _login(client, "seller@empresa.com", "supersecret")
    assert resp.status_code == 401


# --- get_current_user vía /auth/me ------------------------------------------


def test_me_with_valid_token(client):
    _create_user(client)
    token = _login(client, "seller@empresa.com", "supersecret").json()["data"][
        "accessToken"
    ]
    resp = client.get("/api/v1/auth/me", headers=_auth_header(token))
    assert resp.status_code == 200
    assert resp.json()["data"]["email"] == "seller@empresa.com"


def test_me_without_token_returns_401(client):
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401


def test_me_with_invalid_token_returns_401(client):
    resp = client.get("/api/v1/auth/me", headers=_auth_header("garbage.token.value"))
    assert resp.status_code == 401


def test_me_with_token_of_deleted_user_returns_401(client):
    created = _create_user(client).json()["data"]
    token = _login(client, "seller@empresa.com", "supersecret").json()["data"][
        "accessToken"
    ]
    client.delete(f"/api/v1/users/{created['id']}")
    resp = client.get("/api/v1/auth/me", headers=_auth_header(token))
    assert resp.status_code == 401


def test_me_with_nonnumeric_subject_returns_401(client):
    # Token bien firmado pero con un 'sub' no numérico: la dependencia lo rechaza.
    token = create_access_token(subject="no-soy-un-id", role="vendedor")
    resp = client.get("/api/v1/auth/me", headers=_auth_header(token))
    assert resp.status_code == 401


def test_create_user_invalid_role_returns_422(client):
    resp = _create_user(client, role="superusuario")
    assert resp.status_code == 422


# --- Matriz de permisos (spec) ----------------------------------------------


def test_permission_matrix_reflects_roles():
    assert RESOURCE_ROLES["users:manage"] == (UserRole.ADMIN,)
    assert RESOURCE_ROLES["analytics"] == (UserRole.ADMIN,)
    assert RESOURCE_ROLES["products:read"] == (UserRole.ADMIN, UserRole.SELLER)
    # El operador solo entra al plan de corte; no a cotizar/crear órdenes.
    assert UserRole.OPERATOR in RESOURCE_ROLES["cutting_plan"]
    assert UserRole.OPERATOR not in RESOURCE_ROLES["orders:write"]
