from .base import BaseConfig, env


class Config(BaseConfig):
    """Configuración para el entorno de producción"""

    LOG_LEVEL = env("LOG_LEVEL", "WARNING")
    DEBUG = env.bool("DEBUG", False)

    # Configuración específica para producción
    RELOAD = False

    # Base de datos producción (requerida)
    DATABASE_URL = env("DATABASE_URL")  # Sin default, debe estar definida

    # Redis producción
    REDIS_URL = env("REDIS_URL", "redis://redis-prod:6379/0")

    # Seguridad mejorada
    SECRET_KEY = env("SECRET_KEY")  # Sin default, debe estar definida
