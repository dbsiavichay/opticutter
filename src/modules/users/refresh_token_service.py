"""Refresh token lifecycle: issuance, rotation and revocation.

The access token (JWT) is short-lived; the refresh token is long and opaque, and
is exchanged on ``/auth/refresh`` for a new pair. Design:

- **Rotation**: each refresh is used only once. ``rotate`` revokes the presented
  one and issues another, so a valid refresh changes on every renewal.
- **Reuse detection**: if an already-revoked refresh arrives (a theft signal:
  someone reused one that already rotated), **all** of the user's family is
  revoked and the request is rejected.
- **Revocation**: ``revoke`` (logout) and ``revoke_all_for_user`` (password
  change) mark ``revoked_at``.

Only the token's sha256 (``hash_token``) is persisted; the plain-text token only
ever exists in the response sent to the client.
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

# Uniform message: doesn't distinguish nonexistent/expired/revoked (no oracle).
_INVALID = "Sesión inválida o expirada"


class RefreshTokenService:
    """Issues, rotates and revokes refresh tokens against the ``refresh_tokens`` table."""

    def __init__(self, db: Session):
        self.db = db

    def issue(self, user_id: int) -> str:
        """Creates a refresh token for the user and returns the plain-text token."""
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
        """Validates the refresh, revokes it and issues a new one: ``(user, new_token)``."""
        record = self._get(raw)
        if record is None or record.expires_at <= datetime.utcnow():
            raise AuthenticationError(_INVALID)
        if record.revoked_at is not None:
            # Reuse of an already-rotated token: possible theft. Revoke the whole family.
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
        """Revokes a refresh token (logout). No-op if it doesn't exist or is already revoked."""
        record = self._get(raw)
        if record is not None and record.revoked_at is None:
            record.revoked_at = datetime.utcnow()
            self.db.commit()

    def revoke_all_for_user(self, user_id: int) -> None:
        """Revokes all of the user's active refresh tokens (password change)."""
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
    """``RefreshTokenService`` provider for route injection."""
    return RefreshTokenService(db)
