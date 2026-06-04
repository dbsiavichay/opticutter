import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.shared.exceptions import AppError
from src.shared.responses import ErrorDetail, ErrorResponse

logger = logging.getLogger(__name__)

# Nombres de código legibles para errores HTTP que no nacen de un ``AppError``
# (rutas inexistentes, método no permitido, ``HTTPException`` manual).
_HTTP_CODE_NAMES = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    422: "VALIDATION_ERROR",
}


def _error_response(status_code: int, details: list[ErrorDetail]) -> JSONResponse:
    body = ErrorResponse(errors=details)
    return JSONResponse(
        status_code=status_code,
        content=body.model_dump(by_alias=True, mode="json"),
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Registra el manejo centralizado de errores con la envoltura ``{errors, meta}``.

    Cubre los cuatro orígenes: errores de aplicación/dominio (``AppError``),
    validación de request (``RequestValidationError``), ``HTTPException`` del
    framework y cualquier excepción no controlada (catch-all 500).
    """

    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        detail = ErrorDetail(code=exc.code, message=exc.detail, field=exc.field)
        return _error_response(exc.status_code, [detail])

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        details = [
            ErrorDetail(
                code="VALIDATION_ERROR",
                message=err["msg"],
                field=".".join(str(part) for part in err["loc"]),  # p. ej. body.price
            )
            for err in exc.errors()
        ]
        return _error_response(422, details)

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        code = _HTTP_CODE_NAMES.get(exc.status_code, "HTTP_ERROR")
        detail = ErrorDetail(code=code, message=str(exc.detail))
        return _error_response(exc.status_code, [detail])

    @app.exception_handler(Exception)
    async def handle_unhandled_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Excepción no controlada")
        detail = ErrorDetail(
            code="INTERNAL_SERVER_ERROR", message="Error interno del servidor"
        )
        return _error_response(500, [detail])
