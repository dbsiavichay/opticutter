from fastapi import APIRouter, Depends

from src.modules.users.dependencies import get_current_user
from src.modules.users.model import UserModel
from src.modules.users.schemas import LoginRequest, TokenResponse, UserResponse
from src.modules.users.service import UserService, user_service
from src.shared.config import config
from src.shared.exceptions import AuthenticationError
from src.shared.responses import ERROR_RESPONSES, DataResponse, ok
from src.shared.security import create_access_token

router = APIRouter(prefix="/auth", tags=["auth"], responses=ERROR_RESPONSES)


@router.post("/login", response_model=DataResponse[TokenResponse])
def login(data: LoginRequest, svc: UserService = Depends(user_service)):
    """Valida email + contraseña y emite un JWT de acceso."""
    user = svc.authenticate(data.email, data.password)
    if user is None:
        # Mensaje genérico: no revela si el email existe o si fue la contraseña.
        raise AuthenticationError("Email o contraseña incorrectos")
    token = create_access_token(user.id, user.role)
    return ok(
        TokenResponse(
            access_token=token,
            expires_in=config.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=UserResponse.model_validate(user),
        )
    )


@router.get("/me", response_model=DataResponse[UserResponse])
def me(current_user: UserModel = Depends(get_current_user)):
    """Devuelve el usuario autenticado (primer consumidor de la infra de auth)."""
    return ok(current_user)
