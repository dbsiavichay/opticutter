"""Contexto por request: identificador de correlación (requestId) y usuario.

Ambos los fija un middleware ASGI puro al inicio de cada request. El requestId lo
leen la ``Meta`` de las respuestas y los handlers de error; el id de usuario lo
lee ``CRUDService`` para estampar ``created_by``/``updated_by`` sin propagar el
valor por la firma de cada endpoint. Se fijan en middleware (no en una dependencia)
porque las dependencias sync corren en threadpool y su mutación del ContextVar no
propaga al handler.
"""

from contextvars import ContextVar
from typing import Optional
from uuid import uuid4

request_id_ctx: ContextVar[str] = ContextVar("request_id", default="")
current_user_ctx: ContextVar[Optional[int]] = ContextVar(
    "current_user_id", default=None
)


def get_request_id() -> str:
    """requestId del request en curso, o uno nuevo como fallback defensivo."""
    return request_id_ctx.get() or str(uuid4())


def get_current_user_id() -> Optional[int]:
    """Id del usuario autenticado del request en curso, o ``None`` si es público."""
    return current_user_ctx.get()
