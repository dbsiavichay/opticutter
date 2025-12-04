from .base import BaseConfig, env


class Config(BaseConfig):
    """Configuración para el entorno de producción"""

    LOG_LEVEL = env("LOG_LEVEL", "WARNING")
    DEBUG = env.bool("DEBUG", False)

    RELOAD = False

    DATABASE_URL = env("DATABASE_URL")

    REDIS_URL = env("REDIS_URL", "redis://redis-prod:6379/0")

    SECRET_KEY = env("SECRET_KEY")
