"""Tests del módulo users: seguridad, CRUD, login, refresh, autoservicio y RBAC."""

import pytest

from src.modules.users.dependencies import require_permission, require_role
from src.modules.users.enums import UserRole
from src.modules.users.model import UserModel
from src.modules.users.permissions import RESOURCE_ROLES
from src.modules.users.schemas import UserCreate
from src.modules.users.service import UserService
from src.shared.exceptions import AuthenticationError, AuthorizationError
from src.shared.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)

_PWD = "supersecret123"


@pytest.fixture
def client(anon_client):
    """En esta suite ``client`` es el cliente SIN autenticación por defecto.

    Sobreescribe el ``client`` admin-autenticado de ``conftest`` para poder probar
    el login, el refresh y el enforcement por rol controlando el header a mano.
    """
    return anon_client


# Sucursal por defecto sembrada por conftest (id=1); el staff cuelga de ella.
_BRANCH = 1


def _user_payload(
    email="seller@empresa.com",
    password="supersecret",
    role="vendedor",
    full_name="Vendedor Uno",
    branch_id=_BRANCH,
):
    return {
        "email": email,
        "password": password,
        "role": role,
        "fullName": full_name,
        "branchId": branch_id,
    }


def _auth_header(token):
    return {"Authorization": f"Bearer {token}"}


def _login(client, email, password):
    return client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )


def _token(client, email, password=_PWD):
    return _login(client, email, password).json()["data"]["accessToken"]


@pytest.fixture
def auth(client, db_session):
    """Factory de headers Bearer por rol (siembra el usuario y hace login).

    ``auth("administrador")`` -> headers autenticados de un admin. Siembra directo
    en la BD (sin pasar por el CRUD protegido) y reusa la sesión del ``client``.
    """

    def _for(role: str, email: str | None = None):
        email = email or f"{role}@empresa.com"
        svc = UserService(db_session)
        if svc.get_by_email(email) is None:
            # El staff (vendedor/operador) cuelga de la sucursal por defecto; el
            # admin es global (branch_id se ignora y queda en null).
            branch_id = None if role == "administrador" else _BRANCH
            svc.create(
                UserCreate(
                    email=email,
                    password=_PWD,
                    role=role,
                    full_name=role.title(),
                    branch_id=branch_id,
                )
            )
        return _auth_header(_token(client, email))

    return _for


def _create_user(client, headers, **kw):
    return client.post("/api/v1/users/", json=_user_payload(**kw), headers=headers)


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


# --- require_role / require_permission (unitarios) --------------------------


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


def test_require_permission_resolves_matrix():
    dep = require_permission("orders:read")  # admin + vendedor + operador
    assert dep(current_user=_fake_user("operador")).role == "operador"


def test_require_permission_blocks_disallowed_role():
    dep = require_permission("users:manage")  # solo admin
    with pytest.raises(AuthorizationError):
        dep(current_user=_fake_user("vendedor"))


def test_require_permission_unknown_key_raises_keyerror():
    # Un typo en la clave revienta al construir la dependencia (carga del router).
    with pytest.raises(KeyError):
        require_permission("does:not:exist")


# --- CRUD de usuarios (vía API, como admin) ---------------------------------


def test_create_user_hashes_password_and_hides_it(client, auth):
    resp = _create_user(client, auth("administrador"))
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["email"] == "seller@empresa.com"
    assert data["role"] == "vendedor"
    assert data["isActive"] is True
    assert "id" in data
    assert "password" not in data
    assert "hashedPassword" not in data


def test_create_user_role_is_case_insensitive(client, auth):
    resp = _create_user(
        client, auth("administrador"), email="admin2@empresa.com", role="ADMINISTRADOR"
    )
    assert resp.status_code == 201
    assert resp.json()["data"]["role"] == "administrador"


def test_create_duplicate_email_returns_409(client, auth):
    admin = auth("administrador")
    _create_user(client, admin)
    dup = _create_user(client, admin, full_name="Otro")
    assert dup.status_code == 409
    assert dup.json()["errors"][0]["message"] == "El email ya está registrado"


def test_invalid_email_returns_422(client, auth):
    resp = _create_user(client, auth("administrador"), email="no-es-email")
    assert resp.status_code == 422


def test_short_password_returns_422(client, auth):
    resp = _create_user(client, auth("administrador"), password="short")
    assert resp.status_code == 422


def test_get_missing_user_returns_404(client, auth):
    resp = client.get("/api/v1/users/999999", headers=auth("administrador"))
    assert resp.status_code == 404
    assert resp.json()["errors"][0]["code"] == "NOT_FOUND"


def test_list_and_search_users(client, auth):
    admin = auth("administrador")
    _create_user(client, admin, email="ana@empresa.com", full_name="Ana")
    _create_user(client, admin, email="beto@empresa.com", full_name="Beto")
    all_users = client.get("/api/v1/users/", headers=admin)
    assert all_users.status_code == 200
    # El admin sembrado por la fixture también cuenta.
    emails = {u["email"] for u in all_users.json()["data"]}
    assert {"ana@empresa.com", "beto@empresa.com"} <= emails
    found = client.get("/api/v1/users/", params={"search": "ana"}, headers=admin)
    assert [u["email"] for u in found.json()["data"]] == ["ana@empresa.com"]


def test_update_user_fields(client, auth):
    admin = auth("administrador")
    created = _create_user(client, admin).json()["data"]
    resp = client.put(
        f"/api/v1/users/{created['id']}",
        json={"fullName": "Nuevo Nombre", "role": "operador"},
        headers=admin,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["fullName"] == "Nuevo Nombre"
    assert data["role"] == "operador"


def test_update_password_allows_login_with_new_password(client, auth):
    admin = auth("administrador")
    created = _create_user(client, admin).json()["data"]
    client.put(
        f"/api/v1/users/{created['id']}",
        json={"password": "brand-new-pass"},
        headers=admin,
    )
    assert _login(client, "seller@empresa.com", "supersecret").status_code == 401
    assert _login(client, "seller@empresa.com", "brand-new-pass").status_code == 200


def test_delete_user(client, auth):
    admin = auth("administrador")
    created = _create_user(client, admin).json()["data"]
    assert (
        client.delete(f"/api/v1/users/{created['id']}", headers=admin).status_code
        == 204
    )
    assert (
        client.get(f"/api/v1/users/{created['id']}", headers=admin).status_code == 404
    )


def test_create_user_invalid_role_returns_422(client, auth):
    resp = _create_user(client, auth("administrador"), role="superusuario")
    assert resp.status_code == 422


# --- Login / refresh / logout -----------------------------------------------


def test_login_success_returns_token_pair_and_user(client, auth):
    auth("administrador")  # siembra + asegura que el login funciona
    resp = _login(client, "administrador@empresa.com", _PWD)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["tokenType"] == "bearer"
    assert data["accessToken"]
    assert data["refreshToken"]
    assert data["expiresIn"] > 0
    assert data["user"]["email"] == "administrador@empresa.com"
    assert data["user"]["role"] == "administrador"


def test_login_wrong_password_returns_401(client, auth):
    auth("vendedor")
    resp = _login(client, "vendedor@empresa.com", "incorrecta")
    assert resp.status_code == 401
    assert resp.json()["errors"][0]["code"] == "UNAUTHORIZED"


def test_login_unknown_email_returns_401(client):
    resp = _login(client, "nadie@empresa.com", _PWD)
    assert resp.status_code == 401


def test_login_inactive_user_returns_401(client, auth):
    admin = auth("administrador")
    created = _create_user(client, admin).json()["data"]
    client.put(
        f"/api/v1/users/{created['id']}", json={"isActive": False}, headers=admin
    )
    assert _login(client, "seller@empresa.com", "supersecret").status_code == 401


def test_refresh_rotates_tokens_and_invalidates_old(client, auth):
    auth("vendedor")
    first = _login(client, "vendedor@empresa.com", _PWD).json()["data"]
    rotated = client.post(
        "/api/v1/auth/refresh", json={"refreshToken": first["refreshToken"]}
    )
    assert rotated.status_code == 200
    new = rotated.json()["data"]
    assert new["accessToken"] and new["refreshToken"]
    assert new["refreshToken"] != first["refreshToken"]
    # El refresh viejo ya no sirve (rotación).
    reuse = client.post(
        "/api/v1/auth/refresh", json={"refreshToken": first["refreshToken"]}
    )
    assert reuse.status_code == 401


def test_refresh_unknown_token_returns_401(client):
    resp = client.post("/api/v1/auth/refresh", json={"refreshToken": "no-existe"})
    assert resp.status_code == 401


def test_refresh_reuse_revokes_whole_family(client, auth):
    auth("vendedor")
    first = _login(client, "vendedor@empresa.com", _PWD).json()["data"]
    second = client.post(
        "/api/v1/auth/refresh", json={"refreshToken": first["refreshToken"]}
    ).json()["data"]
    # Reusar el primero (ya rotado) dispara la detección de robo.
    assert (
        client.post(
            "/api/v1/auth/refresh", json={"refreshToken": first["refreshToken"]}
        ).status_code
        == 401
    )
    # …y revoca también el segundo (familia entera).
    assert (
        client.post(
            "/api/v1/auth/refresh", json={"refreshToken": second["refreshToken"]}
        ).status_code
        == 401
    )


def test_logout_revokes_refresh_token(client, auth):
    auth("vendedor")
    tokens = _login(client, "vendedor@empresa.com", _PWD).json()["data"]
    assert (
        client.post(
            "/api/v1/auth/logout", json={"refreshToken": tokens["refreshToken"]}
        ).status_code
        == 204
    )
    assert (
        client.post(
            "/api/v1/auth/refresh", json={"refreshToken": tokens["refreshToken"]}
        ).status_code
        == 401
    )


# --- get_current_user vía /auth/me ------------------------------------------


def test_me_with_valid_token(client, auth):
    headers = auth("vendedor")
    resp = client.get("/api/v1/auth/me", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["email"] == "vendedor@empresa.com"


def test_me_without_token_returns_401(client):
    assert client.get("/api/v1/auth/me").status_code == 401


def test_me_with_invalid_token_returns_401(client):
    resp = client.get("/api/v1/auth/me", headers=_auth_header("garbage.token.value"))
    assert resp.status_code == 401


def test_me_with_token_of_deleted_user_returns_401(client, auth):
    admin = auth("administrador")
    created = _create_user(client, admin).json()["data"]
    token = _token(client, "seller@empresa.com", "supersecret")
    client.delete(f"/api/v1/users/{created['id']}", headers=admin)
    assert client.get("/api/v1/auth/me", headers=_auth_header(token)).status_code == 401


def test_me_with_nonnumeric_subject_returns_401(client):
    token = create_access_token(subject="no-soy-un-id", role="vendedor")
    assert client.get("/api/v1/auth/me", headers=_auth_header(token)).status_code == 401


# --- Autoservicio: PATCH /auth/me + change-password -------------------------


def test_update_me_changes_full_name_only(client, auth):
    headers = auth("operador")
    resp = client.patch(
        "/api/v1/auth/me",
        json={"fullName": "Operario Renombrado", "role": "administrador"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["fullName"] == "Operario Renombrado"
    # El rol NO se puede auto-cambiar: el campo extra se ignora.
    assert data["role"] == "operador"


def test_update_me_requires_auth(client):
    assert client.patch("/api/v1/auth/me", json={"fullName": "x"}).status_code == 401


def test_change_password_revokes_sessions_and_rotates_credential(client, auth):
    auth("vendedor")
    session = _login(client, "vendedor@empresa.com", _PWD).json()["data"]
    headers = _auth_header(session["accessToken"])
    resp = client.post(
        "/api/v1/auth/change-password",
        json={"currentPassword": _PWD, "newPassword": "nueva-clave-1"},
        headers=headers,
    )
    assert resp.status_code == 204
    # Los refresh previos quedan revocados (cierre de sesiones abiertas).
    assert (
        client.post(
            "/api/v1/auth/refresh", json={"refreshToken": session["refreshToken"]}
        ).status_code
        == 401
    )
    # La clave vieja deja de servir; la nueva funciona.
    assert _login(client, "vendedor@empresa.com", _PWD).status_code == 401
    assert _login(client, "vendedor@empresa.com", "nueva-clave-1").status_code == 200


def test_change_password_wrong_current_returns_401(client, auth):
    headers = auth("vendedor")
    resp = client.post(
        "/api/v1/auth/change-password",
        json={"currentPassword": "no-es", "newPassword": "otra-clave-1"},
        headers=headers,
    )
    assert resp.status_code == 401


def test_change_password_requires_auth(client):
    resp = client.post(
        "/api/v1/auth/change-password",
        json={"currentPassword": "x", "newPassword": "yyyyyyyy"},
    )
    assert resp.status_code == 401


# --- Enforcement por permiso (representativo de la matriz) ------------------


def test_users_endpoint_requires_admin(client, auth):
    assert client.get("/api/v1/users/").status_code == 401  # sin token
    assert client.get("/api/v1/users/", headers=auth("vendedor")).status_code == 403
    assert (
        client.get("/api/v1/users/", headers=auth("administrador")).status_code == 200
    )


def test_products_read_allows_seller(client, auth):
    assert client.get("/api/v1/products/", headers=auth("vendedor")).status_code == 200
    # El operador no entra al catálogo.
    assert client.get("/api/v1/products/", headers=auth("operador")).status_code == 403


def test_products_write_requires_admin(client, auth):
    # DELETE no lleva body: la autorización decide antes de tocar el recurso.
    assert (
        client.delete("/api/v1/products/999", headers=auth("vendedor")).status_code
        == 403
    )
    # El admin pasa la autorización; el 404 (no existe) prueba que se permitió.
    assert (
        client.delete("/api/v1/products/999", headers=auth("administrador")).status_code
        == 404
    )


def test_analytics_is_admin_only(client, auth):
    assert (
        client.get("/api/v1/analytics/summary", headers=auth("vendedor")).status_code
        == 403
    )
    assert (
        client.get(
            "/api/v1/analytics/summary", headers=auth("administrador")
        ).status_code
        == 200
    )


def test_settings_is_admin_only(client, auth):
    assert (
        client.get("/api/v1/settings/cutting", headers=auth("vendedor")).status_code
        == 403
    )
    assert (
        client.get(
            "/api/v1/settings/cutting", headers=auth("administrador")
        ).status_code
        == 200
    )


def test_clients_block_operator_allow_seller(client, auth):
    assert client.get("/api/v1/clients/", headers=auth("operador")).status_code == 403
    assert client.get("/api/v1/clients/", headers=auth("vendedor")).status_code == 200


def test_orders_read_allows_operator(client, auth):
    assert client.get("/api/v1/orders/", headers=auth("operador")).status_code == 200


def test_orders_write_blocks_operator(client, auth):
    resp = client.patch("/api/v1/orders/999/status", json={}, headers=auth("operador"))
    assert resp.status_code == 403


def test_cutting_plan_allows_operator(client, auth):
    # Permitido para operador: el 404 (orden inexistente) prueba que pasó la auth.
    resp = client.get("/api/v1/orders/999/cutting-plan", headers=auth("operador"))
    assert resp.status_code != 403
    assert resp.status_code != 401


def test_public_endpoints_need_no_auth(client):
    assert client.get("/api/v1/health/").status_code == 200
    # El flujo público de revisión se autentica solo por token: sin él, 404 uniforme.
    assert client.get("/api/v1/public/review/token-desconocido").status_code == 404


# --- Matriz de permisos (spec) ----------------------------------------------


def test_permission_matrix_reflects_roles():
    assert RESOURCE_ROLES["users:manage"] == (UserRole.ADMIN,)
    assert RESOURCE_ROLES["analytics"] == (UserRole.ADMIN,)
    assert RESOURCE_ROLES["products:read"] == (UserRole.ADMIN, UserRole.SELLER)
    assert UserRole.OPERATOR in RESOURCE_ROLES["cutting_plan"]
    assert UserRole.OPERATOR not in RESOURCE_ROLES["orders:write"]
