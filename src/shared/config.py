from typing import List

from environs import Env

env = Env()


class Config:
    """Configuración única de la aplicación.

    Lee de variables de entorno; los defaults dependen de ``ENVIRONMENT``.
    Reemplaza la antigua división en ``core/config/{base,local,staging,production}.py``.
    """

    ENVIRONMENT = env("ENVIRONMENT", "local")

    LOG_LEVEL = env(
        "LOG_LEVEL",
        {"local": "DEBUG", "staging": "INFO", "production": "WARNING"}.get(
            ENVIRONMENT, "INFO"
        ),
    )
    DEBUG = env.bool("DEBUG", ENVIRONMENT == "local")
    RELOAD = ENVIRONMENT == "local"

    HOST = env("HOST", "0.0.0.0")
    PORT = env.int("PORT", 3000)

    DEFAULT_TIMEZONE = env("DEFAULT_TIMEZONE", "America/Guayaquil")

    CORS_ORIGINS = env.list(
        "CORS_ORIGINS",
        [
            "http://localhost:3000",
            "http://localhost:3001",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:3001",
        ],
    )

    # DATABASE_URL es obligatorio en producción; con default en otros entornos.
    DATABASE_URL = (
        env("DATABASE_URL")
        if ENVIRONMENT == "production"
        else env(
            "DATABASE_URL",
            "sqlite:///./cutter_local.db" if ENVIRONMENT == "local" else "",
        )
    )

    REDIS_URL = env(
        "REDIS_URL",
        {
            "local": "redis://localhost:6379/0",
            "staging": "redis://redis-staging:6379/0",
            "production": "redis://redis-prod:6379/0",
        }.get(ENVIRONMENT, "redis://localhost:6379/0"),
    )

    SECRET_KEY = (
        env("SECRET_KEY") if ENVIRONMENT == "production" else env("SECRET_KEY", "")
    )

    # Parámetros de corte (mm)
    KERF = env.float("KERF", 5.0)
    TOP_TRIM = env.float("TOP_TRIM", 0.0)
    BOTTOM_TRIM = env.float("BOTTOM_TRIM", 0.0)
    LEFT_TRIM = env.float("LEFT_TRIM", 0.0)
    RIGHT_TRIM = env.float("RIGHT_TRIM", 0.0)

    OPT_RESULT_TTL_SECONDS = env.int("OPT_RESULT_TTL_SECONDS", 259200)

    # Datos de la empresa para la proforma PDF
    COMPANY_NAME = env("COMPANY_NAME", "EMPRESA MADERABLE S.A.")
    COMPANY_RUC = env("COMPANY_RUC", "1234567890001")
    COMPANY_ADDRESS = env("COMPANY_ADDRESS", "Av. Principal 123")
    COMPANY_PHONE = env("COMPANY_PHONE", "(02) 234-5678")
    COMPANY_EMAIL = env("COMPANY_EMAIL", "info@maderable.com")

    def get_cors_origins(self) -> List[str]:
        """Lista de orígenes permitidos para CORS."""
        return self.CORS_ORIGINS

    def is_development(self) -> bool:
        return self.ENVIRONMENT in ["local", "development"]

    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"


config = Config()
