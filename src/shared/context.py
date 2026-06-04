"""Contexto por request: identificador de correlación (requestId).

Lo fija ``RequestIDMiddleware`` (ASGI puro) al inicio de cada request y lo leen
tanto la ``Meta`` de las respuestas como los handlers de error, sin tener que
propagar el valor por la firma de cada endpoint.
"""

from contextvars import ContextVar
from uuid import uuid4

request_id_ctx: ContextVar[str] = ContextVar("request_id", default="")


def get_request_id() -> str:
    """requestId del request en curso, o uno nuevo como fallback defensivo."""
    return request_id_ctx.get() or str(uuid4())
