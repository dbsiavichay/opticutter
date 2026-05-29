from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from src.shared.exceptions import AppError


def register_exception_handlers(app: FastAPI) -> None:
    """Registra el manejo centralizado de errores de aplicación.

    Permite que servicios y dominio lancen ``AppError`` (y subclases) sin
    conocer FastAPI; aquí se traducen a respuestas HTTP con su ``status_code``.
    """

    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )
