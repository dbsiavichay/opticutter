"""Per-request context: correlation id (requestId) and user.

Both are set by a pure ASGI middleware at the start of every request. The
requestId is read by the response ``Meta`` and error handlers; the user id is
read by ``CRUDService`` to stamp ``created_by``/``updated_by`` without
propagating the value through every endpoint's signature. They are set in
middleware (not in a dependency) because sync dependencies run in a
threadpool and their ContextVar mutation doesn't propagate to the handler.
"""

from contextvars import ContextVar
from typing import Optional
from uuid import uuid4

request_id_ctx: ContextVar[str] = ContextVar("request_id", default="")
current_user_ctx: ContextVar[Optional[int]] = ContextVar(
    "current_user_id", default=None
)


def get_request_id() -> str:
    """requestId of the current request, or a new one as a defensive fallback."""
    return request_id_ctx.get() or str(uuid4())


def get_current_user_id() -> Optional[int]:
    """Id of the authenticated user for the current request, or ``None`` if public."""
    return current_user_ctx.get()
