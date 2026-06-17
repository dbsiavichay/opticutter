"""Middlewares ASGI puros para contexto por request.

Se usa ASGI puro (no ``BaseHTTPMiddleware``): este último ejecuta el endpoint en
otra task y el ``ContextVar`` fijado antes de ``call_next`` no siempre propaga.
ASGI puro corre en la misma task, así que el requestId queda visible durante la
serialización del ``response_model`` (donde ``Meta`` lo lee) y el id de usuario
queda visible para los servicios invocados desde el handler.
"""

from uuid import uuid4

from src.shared.context import current_user_ctx, request_id_ctx
from src.shared.security import decode_access_token


class RequestIDMiddleware:
    """Asigna un requestId por request y lo devuelve en el header ``X-Request-ID``.

    Respeta un ``X-Request-ID`` entrante (continuidad de traza, p. ej. desde el
    bot) o genera uno nuevo.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope["headers"])
        request_id = headers.get(b"x-request-id", b"").decode() or str(uuid4())
        token = request_id_ctx.set(request_id)

        async def send_with_request_id(message):
            if message["type"] == "http.response.start":
                message["headers"].append((b"x-request-id", request_id.encode()))
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        finally:
            request_id_ctx.reset(token)


class CurrentUserMiddleware:
    """Fija el id del usuario autenticado en el contexto para auditoría genérica.

    Decodifica el ``Authorization: Bearer`` de forma best-effort: un token ausente
    o inválido deja ``current_user_ctx`` en ``None`` (la dependencia de auth sigue
    devolviendo 401 donde corresponda). Solo necesita el ``sub`` (id) del JWT, que
    ``CRUDService`` usa para estampar ``created_by``/``updated_by``.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        token = current_user_ctx.set(self._resolve_user_id(scope))
        try:
            await self.app(scope, receive, send)
        finally:
            current_user_ctx.reset(token)

    @staticmethod
    def _resolve_user_id(scope):
        headers = dict(scope["headers"])
        auth = headers.get(b"authorization", b"").decode()
        scheme, _, credentials = auth.partition(" ")
        if scheme.lower() != "bearer" or not credentials:
            return None
        try:
            return int(decode_access_token(credentials).get("sub"))
        except Exception:
            return None
