"""Dependencias de autenticación y autorización.

``get_current_user`` resuelve el usuario autenticado desde el JWT y ``require_role``
restringe por rol. Hoy solo las consume ``GET /auth/me``; el resto de endpoints
del sistema siguen abiertos. En la fase de *enforcement* se aplicará ``require_role``
a cada ruta según la matriz documentada en ``permissions.py``.
"""

from typing import Optional

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.modules.users.enums import UserRole
from src.modules.users.model import UserModel
from src.modules.users.service import UserService, user_service
from src.shared.exceptions import AuthenticationError, AuthorizationError
from src.shared.security import decode_access_token

# auto_error=False: gestionamos nosotros el 401 vía AuthenticationError para que
# pase por la envoltura uniforme {errors, meta} en lugar del HTTPException de FastAPI.
bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
    svc: UserService = Depends(user_service),
) -> UserModel:
    """Resuelve el usuario autenticado a partir del ``Authorization: Bearer <jwt>``."""
    if credentials is None or not credentials.credentials:
        raise AuthenticationError("Falta el token de autenticación")
    payload = decode_access_token(credentials.credentials)
    try:
        user_id = int(payload.get("sub"))
    except (TypeError, ValueError) as exc:
        raise AuthenticationError("Token de sesión inválido") from exc
    user = svc.get(user_id)
    if user is None or not user.is_active:
        raise AuthenticationError("Usuario no encontrado o inactivo")
    return user


def require_role(*roles: UserRole):
    """Factory de dependencia: exige que el usuario tenga uno de ``roles``.

    Listo para usar en la fase de enforcement, p. ej.
    ``Depends(require_role(UserRole.ADMIN))`` en el CRUD de usuarios.
    """
    allowed = {role.value for role in roles}

    def dependency(current_user: UserModel = Depends(get_current_user)) -> UserModel:
        if current_user.role not in allowed:
            raise AuthorizationError("No tienes permiso para realizar esta acción")
        return current_user

    return dependency
