from fastapi import APIRouter, Depends, Request

from src.modules.users.dependencies import get_current_user
from src.modules.users.login_event_service import (
    LoginEventService,
    login_event_service,
)
from src.modules.users.model import UserModel
from src.modules.users.refresh_token_service import (
    RefreshTokenService,
    refresh_token_service,
)
from src.modules.users.schemas import (
    ChangePasswordRequest,
    LoginRequest,
    ProfileUpdate,
    RefreshRequest,
    TokenResponse,
    UserResponse,
)
from src.modules.users.service import UserService, user_service
from src.shared.config import config
from src.shared.exceptions import AuthenticationError
from src.shared.responses import ERROR_RESPONSES, DataResponse, ok
from src.shared.security import create_access_token

router = APIRouter(prefix="/auth", tags=["auth"], responses=ERROR_RESPONSES)


def _token_response(user: UserModel, refresh_token: str) -> TokenResponse:
    """Arma el par de tokens (access JWT + refresh) y los datos del usuario."""
    return TokenResponse(
        access_token=create_access_token(user.id, user.role),
        refresh_token=refresh_token,
        expires_in=config.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserResponse.model_validate(user),
    )


@router.post("/login", response_model=DataResponse[TokenResponse])
def login(
    data: LoginRequest,
    request: Request,
    svc: UserService = Depends(user_service),
    refresh_svc: RefreshTokenService = Depends(refresh_token_service),
    login_event_svc: LoginEventService = Depends(login_event_service),
):
    """Valida email + contraseña y emite un par access/refresh."""
    user = svc.authenticate(data.email, data.password)
    if user is None:
        # Mensaje genérico: no revela si el email existe o si fue la contraseña.
        raise AuthenticationError("Email o contraseña incorrectos")
    # Registra la entrada (referencia de "hora de entrada"); solo en login, no refresh.
    login_event_svc.record(
        user.id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return ok(_token_response(user, refresh_svc.issue(user.id)))


@router.post("/refresh", response_model=DataResponse[TokenResponse])
def refresh(
    data: RefreshRequest,
    refresh_svc: RefreshTokenService = Depends(refresh_token_service),
):
    """Canjea un refresh token por un par nuevo (rota el presentado)."""
    user, new_refresh = refresh_svc.rotate(data.refresh_token)
    return ok(_token_response(user, new_refresh))


@router.post("/logout", status_code=204)
def logout(
    data: RefreshRequest,
    refresh_svc: RefreshTokenService = Depends(refresh_token_service),
):
    """Cierra la sesión revocando el refresh token presentado (idempotente)."""
    refresh_svc.revoke(data.refresh_token)


@router.get("/me", response_model=DataResponse[UserResponse])
def me(current_user: UserModel = Depends(get_current_user)):
    """Devuelve el usuario autenticado."""
    return ok(current_user)


@router.patch("/me", response_model=DataResponse[UserResponse])
def update_me(
    data: ProfileUpdate,
    current_user: UserModel = Depends(get_current_user),
    svc: UserService = Depends(user_service),
):
    """Autoservicio: el propio usuario edita su perfil (solo ``fullName``)."""
    return ok(svc.update_profile(current_user, data))


@router.post("/change-password", status_code=204)
def change_password(
    data: ChangePasswordRequest,
    current_user: UserModel = Depends(get_current_user),
    svc: UserService = Depends(user_service),
    refresh_svc: RefreshTokenService = Depends(refresh_token_service),
):
    """Autoservicio: cambia la propia contraseña y revoca las sesiones abiertas."""
    svc.change_password(current_user, data.current_password, data.new_password)
    refresh_svc.revoke_all_for_user(current_user.id)
