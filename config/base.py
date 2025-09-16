from typing import List

from environs import Env

env = Env()


class BaseConfig:
    """Configuración base para todos los entornos"""

    # Configuración básica
    LOG_LEVEL = env("LOG_LEVEL", "INFO")
    ENVIRONMENT = env("ENVIRONMENT", "local")
    DEBUG = env.bool("DEBUG", False)

    # Configuración del servidor
    HOST = env("HOST", "0.0.0.0")
    PORT = env.int("PORT", 3000)

    # Timezone
    DEFAULT_TIMEZONE = env("DEFAULT_TIMEZONE", "America/Guayaquil")

    # CORS
    CORS_ORIGINS = env.list(
        "CORS_ORIGINS", ["http://localhost:3000", "http://localhost:3001"]
    )

    # Base de datos (para futuro uso)
    DATABASE_URL = env("DATABASE_URL", "")

    # Redis (para caching de optimizaciones)
    REDIS_URL = env("REDIS_URL", "redis://localhost:6379/0")

    # Cutting optimizer params
    KERF = env.float("KERF", 5.0)
    TOP_TRIM = env.float("TOP_TRIM", 0.0)
    BOTTOM_TRIM = env.float("BOTTOM_TRIM", 0.0)
    LEFT_TRIM = env.float("LEFT_TRIM", 0.0)
    RIGHT_TRIM = env.float("RIGHT_TRIM", 0.0)

    # Caching / TTLs
    OPT_RESULT_TTL_SECONDS = env.int("OPT_RESULT_TTL_SECONDS", 259200)  # 3 días

    def get_cors_origins(self) -> List[str]:
        """Obtiene la lista de orígenes permitidos para CORS"""
        return self.CORS_ORIGINS

    def is_development(self) -> bool:
        """Verifica si está en modo desarrollo"""
        return self.ENVIRONMENT in ["local", "development"]

    def is_production(self) -> bool:
        """Verifica si está en modo producción"""
        return self.ENVIRONMENT == "production"
