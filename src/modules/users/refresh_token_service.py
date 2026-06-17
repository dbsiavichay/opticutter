"""Ciclo de vida de los refresh tokens: emisión, rotación y revocación.

El access token (JWT) es corto; el refresh es largo y opaco, y se canjea en
``/auth/refresh`` por un par nuevo. Diseño:

- **Rotación**: cada refresh se usa una sola vez. ``rotate`` revoca el presentado
  y emite otro, de modo que un refresh válido cambia en cada renovación.
- **Detección de reúso**: si llega un refresh ya revocado (señal de robo: alguien
  reusó uno que ya rotó), se revoca **toda** la familia del usuario y se rechaza.
- **Revocación**: ``revoke`` (logout) y ``revoke_all_for_user`` (cambio de
  contraseña) marcan ``revoked_at``.

Solo se persiste el sha256 del token (``hash_token``); el token en claro existe
únicamente en la respuesta al cliente.
"""

from datetime import datetime, timedelta
from typing import Optional, Tuple

from fastapi import Depends
from sqlalchemy.orm import Session

from src.modules.users.model import UserModel
from src.modules.users.refresh_token_model import RefreshTokenModel
from src.shared.config import config
from src.shared.database import get_db
from src.shared.exceptions import AuthenticationError
from src.shared.security import generate_refresh_token, hash_token

# Mensaje uniforme: no distingue inexistente/expirado/revocado (sin oráculo).
_INVALID = "Sesión inválida o expirada"


class RefreshTokenService:
    """Emite, rota y revoca refresh tokens contra la tabla ``refresh_tokens``."""

    def __init__(self, db: Session):
        self.db = db

    def issue(self, user_id: int) -> str:
        """Crea un refresh token para el usuario y devuelve el token en claro."""
        raw = generate_refresh_token()
        self.db.add(
            RefreshTokenModel(
                user_id=user_id,
                token_hash=hash_token(raw),
                expires_at=self._expiry(),
            )
        )
        self.db.commit()
        return raw

    def rotate(self, raw: str) -> Tuple[UserModel, str]:
        """Valida el refresh, lo revoca y emite uno nuevo: ``(usuario, token_nuevo)``."""
        record = self._get(raw)
        if record is None or record.expires_at <= datetime.utcnow():
            raise AuthenticationError(_INVALID)
        if record.revoked_at is not None:
            # Reúso de un token ya rotado: posible robo. Revoca toda la familia.
            self.revoke_all_for_user(record.user_id)
            raise AuthenticationError(_INVALID)

        user = self.db.get(UserModel, record.user_id)
        if user is None or not user.is_active:
            raise AuthenticationError("Usuario no encontrado o inactivo")

        record.revoked_at = datetime.utcnow()
        raw_new = generate_refresh_token()
        self.db.add(
            RefreshTokenModel(
                user_id=user.id,
                token_hash=hash_token(raw_new),
                expires_at=self._expiry(),
            )
        )
        self.db.commit()
        return user, raw_new

    def revoke(self, raw: str) -> None:
        """Revoca un refresh token (logout). No-op si no existe o ya está revocado."""
        record = self._get(raw)
        if record is not None and record.revoked_at is None:
            record.revoked_at = datetime.utcnow()
            self.db.commit()

    def revoke_all_for_user(self, user_id: int) -> None:
        """Revoca todos los refresh tokens activos del usuario (cambio de contraseña)."""
        self.db.query(RefreshTokenModel).filter(
            RefreshTokenModel.user_id == user_id,
            RefreshTokenModel.revoked_at.is_(None),
        ).update({RefreshTokenModel.revoked_at: datetime.utcnow()})
        self.db.commit()

    def _get(self, raw: str) -> Optional[RefreshTokenModel]:
        return (
            self.db.query(RefreshTokenModel)
            .filter(RefreshTokenModel.token_hash == hash_token(raw))
            .first()
        )

    @staticmethod
    def _expiry() -> datetime:
        return datetime.utcnow() + timedelta(days=config.REFRESH_TOKEN_EXPIRE_DAYS)


def refresh_token_service(db: Session = Depends(get_db)) -> RefreshTokenService:
    """Provider de ``RefreshTokenService`` para inyección en rutas."""
    return RefreshTokenService(db)
