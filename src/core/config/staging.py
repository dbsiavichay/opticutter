from .base import BaseConfig, env


class Config(BaseConfig):
    """Configuración para el entorno de staging"""

    LOG_LEVEL = env("LOG_LEVEL", "INFO")
    DEBUG = env.bool("DEBUG", False)

    RELOAD = False

    DATABASE_URL = env("DATABASE_URL", "")

    REDIS_URL = env("REDIS_URL", "redis://redis-staging:6379/0")
