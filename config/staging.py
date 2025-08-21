from .base import BaseConfig, env


class Config(BaseConfig):
    """Configuración para el entorno de staging"""

    LOG_LEVEL = env("LOG_LEVEL", "INFO")
    DEBUG = env.bool("DEBUG", False)

    # Configuración específica para staging
    RELOAD = False

    # Base de datos staging
    DATABASE_URL = env("DATABASE_URL", "")

    # Redis staging
    REDIS_URL = env("REDIS_URL", "redis://redis-staging:6379/0")
