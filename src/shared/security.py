"""Primitivas de seguridad: hash de contraseñas y JWT.

Infraestructura sin dependencias de FastAPI/SQLAlchemy. El módulo de usuarios
(``src/modules/users``) construye sobre estos helpers el login y la dependencia
``get_current_user``. Lee la configuración (``SECRET_KEY``, algoritmo y vigencia)
de ``shared.config``.
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt

from src.shared.config import config
from src.shared.exceptions import AuthenticationError

# bcrypt opera sobre, como mucho, 72 bytes: truncamos para que contraseñas largas
# no exploten ni cambien de comportamiento entre versiones de la librería.
_BCRYPT_MAX_BYTES = 72


def _encode_password(plain: str) -> bytes:
    return plain.encode("utf-8")[:_BCRYPT_MAX_BYTES]


def hash_password(plain: str) -> str:
    """Devuelve el hash bcrypt de una contraseña en claro (almacenable como texto)."""
    salt = bcrypt.gensalt(rounds=config.BCRYPT_ROUNDS)
    return bcrypt.hashpw(_encode_password(plain), salt).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Compara una contraseña en claro contra su hash bcrypt."""
    try:
        return bcrypt.checkpw(_encode_password(plain), hashed.encode("utf-8"))
    except ValueError:
        # Hash con formato inválido (datos corruptos): trátalo como no coincidente.
        return False


def create_access_token(
    subject: str | int, role: str, expires_minutes: Optional[int] = None
) -> str:
    """Emite un JWT firmado con ``sub`` (id del usuario), ``role``, ``iat`` y ``exp``."""
    minutes = (
        expires_minutes
        if expires_minutes is not None
        else config.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(subject),
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=minutes),
    }
    return jwt.encode(payload, config.SECRET_KEY, algorithm=config.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Decodifica y valida un JWT; lanza ``AuthenticationError`` si no es válido."""
    try:
        return jwt.decode(token, config.SECRET_KEY, algorithms=[config.JWT_ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise AuthenticationError("El token de sesión expiró") from exc
    except jwt.InvalidTokenError as exc:
        raise AuthenticationError("Token de sesión inválido") from exc


def generate_refresh_token() -> str:
    """Genera un refresh token opaco de 256 bits (CSPRNG).

    Es la credencial que canjea ``/auth/refresh`` por un nuevo access token. Opaco
    (no JWT) para poder revocarlo: en reposo solo se guarda su ``hash_token``.
    """
    return secrets.token_urlsafe(32)


def hash_token(raw: str) -> str:
    """sha256 hex de un token opaco. Se persiste el hash, nunca el token en claro.

    Un token aleatorio de 256 bits es su propio salt, por eso sha256 sin salt basta
    (mismo criterio que los enlaces de revisión de pre-órdenes).
    """
    return hashlib.sha256(raw.encode()).hexdigest()
