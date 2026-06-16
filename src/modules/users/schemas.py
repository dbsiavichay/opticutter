from datetime import datetime
from typing import Optional

from pydantic import EmailStr, Field

from src.modules.users.enums import UserRole
from src.shared.schemas import CamelModel


class UserBase(CamelModel):
    email: EmailStr = Field(..., description="Email de login (único)")
    full_name: Optional[str] = Field(
        None, max_length=128, description="Nombre completo"
    )
    role: UserRole = Field(
        default=UserRole.OPERATOR,
        description="Rol: administrador, vendedor u operador",
    )


class UserCreate(UserBase):
    """Alta de usuario. La contraseña viaja en claro solo aquí; se hashea al persistir."""

    password: str = Field(..., min_length=8, max_length=128, description="Contraseña")


class UserUpdate(CamelModel):
    """Actualización parcial. Enviar ``password`` la rehashea; ``isActive`` da de baja."""

    email: Optional[EmailStr] = Field(None, description="Email de login (único)")
    full_name: Optional[str] = Field(
        None, max_length=128, description="Nombre completo"
    )
    role: Optional[UserRole] = Field(None, description="Rol del usuario")
    is_active: Optional[bool] = Field(None, description="Activo/inactivo (baja lógica)")
    password: Optional[str] = Field(
        None, min_length=8, max_length=128, description="Nueva contraseña"
    )


class UserResponse(UserBase):
    """Representación pública de un usuario. Nunca incluye la contraseña ni su hash."""

    id: int = Field(..., description="ID del usuario")
    is_active: bool = Field(..., description="Activo/inactivo")
    created_at: datetime = Field(..., description="Fecha de creación")


class LoginRequest(CamelModel):
    email: EmailStr = Field(..., description="Email de login")
    password: str = Field(..., description="Contraseña")


class TokenResponse(CamelModel):
    """Respuesta del login: token de acceso + datos del usuario autenticado."""

    access_token: str = Field(..., description="JWT de acceso")
    token_type: str = Field(default="bearer", description="Tipo de token")
    expires_in: int = Field(..., description="Vigencia del token en segundos")
    user: UserResponse = Field(..., description="Usuario autenticado")
