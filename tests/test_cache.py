"""Tests del helper de caché: round-trip JSON y degradación elegante."""

import redis

from src.shared.cache import CacheService


class _FakeRedis:
    """Doble en memoria que parea ``get``/``set`` (como ``decode_responses=True``)."""

    def __init__(self):
        self._store = {}

    def get(self, key):
        return self._store.get(key)

    def set(self, key, value, ex=None):
        self._store[key] = value
        return True


class _BrokenRedis:
    """Doble que simula Redis caído: toda operación lanza ``ConnectionError``."""

    def get(self, key):
        raise redis.ConnectionError("redis down")

    def set(self, key, value, ex=None):
        raise redis.ConnectionError("redis down")


def test_set_and_get_json_round_trip():
    svc = CacheService(client=_FakeRedis())
    value = {"a": 1, "nested": [1, 2, {"b": True}], "s": "x"}
    svc.set_json("k", value, ttl=60)
    assert svc.get_json("k") == value


def test_get_json_missing_key_returns_none():
    svc = CacheService(client=_FakeRedis())
    assert svc.get_json("missing") is None


def test_get_json_degrades_on_redis_error():
    svc = CacheService(client=_BrokenRedis())
    assert svc.get_json("k") is None


def test_set_json_degrades_on_redis_error():
    svc = CacheService(client=_BrokenRedis())
    # No debe propagar la excepción: la caché es acelerador, no fuente de verdad.
    svc.set_json("k", {"x": 1})
