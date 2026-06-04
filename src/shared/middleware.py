"""Middleware ASGI puro para correlación de requests.

Se usa ASGI puro (no ``BaseHTTPMiddleware``): este último ejecuta el endpoint en
otra task y el ``ContextVar`` fijado antes de ``call_next`` no siempre propaga.
ASGI puro corre en la misma task, así que el requestId queda visible durante la
serialización del ``response_model`` (donde ``Meta`` lo lee).
"""

from uuid import uuid4

from src.shared.context import request_id_ctx


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
