"""Shared Redis-backed cache with JSON (de)serialization and graceful degradation.

The cache is an *accelerator*, not the source of truth: if Redis doesn't
respond, ``get_json`` returns ``None`` and ``set_json`` is a no-op, so the
caller simply recomputes. The client is created lazily and can be injected in
tests (``CacheService(client=...)``).
"""

import json
import logging
from typing import Any, Optional

import redis

from src.shared.config import config

logger = logging.getLogger(__name__)


class CacheService:
    """JSON wrapper over a fault-tolerant Redis client."""

    def __init__(self, client: Optional["redis.Redis"] = None):
        self._client = client
        self._initialized = client is not None

    @property
    def client(self) -> Optional["redis.Redis"]:
        """Lazy Redis client; ``None`` if it couldn't be initialized."""
        if not self._initialized:
            try:
                self._client = redis.Redis.from_url(
                    config.REDIS_URL,
                    socket_connect_timeout=0.5,
                    socket_timeout=0.5,
                    decode_responses=True,
                )
            except (redis.RedisError, ValueError) as exc:  # pragma: no cover
                logger.warning("Could not initialize Redis: %s", exc)
                self._client = None
            self._initialized = True
        return self._client

    def get_json(self, key: str) -> Optional[Any]:
        """Returns the deserialized value, or ``None`` if missing or Redis fails."""
        client = self.client
        if client is None:
            return None
        try:
            raw = client.get(key)
        except redis.RedisError as exc:
            logger.warning("Cache get failed (%s): %s", key, exc)
            return None
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except (TypeError, ValueError):
            return None

    def set_json(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Serializes and stores ``value`` with expiration; no-op if Redis fails."""
        client = self.client
        if client is None:
            return
        ttl = ttl if ttl is not None else config.OPT_RESULT_TTL_SECONDS
        try:
            client.set(key, json.dumps(value), ex=ttl)
        except redis.RedisError as exc:
            logger.warning("Cache set failed (%s): %s", key, exc)


# Shared instance; services import ``cache`` and use it directly.
cache = CacheService()
