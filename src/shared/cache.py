"""Caché compartida sobre Redis con (de)serialización JSON y degradación elegante.

La caché es un *acelerador*, no la fuente de verdad: si Redis no responde,
``get_json`` devuelve ``None`` y ``set_json`` es un no-op, de modo que el llamador
simplemente recalcula. El cliente se crea de forma perezosa y puede inyectarse en
tests (``CacheService(client=...)``).
"""

import json
import logging
from typing import Any, Optional

import redis

from src.shared.config import config

logger = logging.getLogger(__name__)


class CacheService:
    """Envoltorio JSON sobre un cliente Redis tolerante a fallos."""

    def __init__(self, client: Optional["redis.Redis"] = None):
        self._client = client
        self._initialized = client is not None

    @property
    def client(self) -> Optional["redis.Redis"]:
        """Cliente Redis perezoso; ``None`` si no se pudo inicializar."""
        if not self._initialized:
            try:
                self._client = redis.Redis.from_url(
                    config.REDIS_URL,
                    socket_connect_timeout=0.5,
                    socket_timeout=0.5,
                    decode_responses=True,
                )
            except (redis.RedisError, ValueError) as exc:  # pragma: no cover
                logger.warning("No se pudo inicializar Redis: %s", exc)
                self._client = None
            self._initialized = True
        return self._client

    def get_json(self, key: str) -> Optional[Any]:
        """Devuelve el valor deserializado, o ``None`` si no existe o Redis falla."""
        client = self.client
        if client is None:
            return None
        try:
            raw = client.get(key)
        except redis.RedisError as exc:
            logger.warning("Cache get falló (%s): %s", key, exc)
            return None
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except (TypeError, ValueError):
            return None

    def set_json(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Serializa y guarda ``value`` con expiración; no-op si Redis falla."""
        client = self.client
        if client is None:
            return
        ttl = ttl if ttl is not None else config.OPT_RESULT_TTL_SECONDS
        try:
            client.set(key, json.dumps(value), ex=ttl)
        except redis.RedisError as exc:
            logger.warning("Cache set falló (%s): %s", key, exc)


# Instancia compartida; los servicios importan ``cache`` y lo usan directamente.
cache = CacheService()
