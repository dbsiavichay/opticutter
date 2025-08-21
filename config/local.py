from .base import BaseConfig, env


class Config(BaseConfig):
    """Configuración para el entorno local/desarrollo"""

    LOG_LEVEL = env("LOG_LEVEL", "DEBUG")
    DEBUG = env.bool("DEBUG", True)

    # Configuración específica para desarrollo
    RELOAD = True

    # Base de datos local (ejemplo)
    DATABASE_URL = env("DATABASE_URL", "sqlite:///./cutter_local.db")

    # Redis local
    REDIS_URL = env("REDIS_URL", "redis://localhost:6379/0")
