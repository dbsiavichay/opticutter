"""Pure ASGI middlewares for per-request context.

Pure ASGI is used (not ``BaseHTTPMiddleware``): the latter runs the endpoint
in a different task, and the ``ContextVar`` set before ``call_next`` doesn't
always propagate. Pure ASGI runs in the same task, so the requestId stays
visible during ``response_model`` serialization (where ``Meta`` reads it) and
the user id stays visible to services invoked from the handler.
"""

from uuid import uuid4

from src.shared.context import current_user_ctx, request_id_ctx
from src.shared.security import decode_access_token


class RequestIDMiddleware:
    """Assigns a requestId per request and returns it in the ``X-Request-ID`` header.

    Honors an incoming ``X-Request-ID`` (trace continuity, e.g. from the bot)
    or generates a new one.
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
    """Sets the authenticated user's id in context for generic auditing.

    Decodes the ``Authorization: Bearer`` header on a best-effort basis: a
    missing or invalid token leaves ``current_user_ctx`` as ``None`` (the auth
    dependency still returns 401 where applicable). It only needs the JWT's
    ``sub`` (id), which ``CRUDService`` uses to stamp ``created_by``/``updated_by``.
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
