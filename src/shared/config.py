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

    # Parámetros de corte (mm). Solo siembran la fila singleton de `settings` en su
    # primera lectura; la fuente de verdad en runtime es la tabla `settings`
    # (editable vía PATCH /settings/cutting).
    KERF = env.float("KERF", 5.0)
    TOP_TRIM = env.float("TOP_TRIM", 0.0)
    BOTTOM_TRIM = env.float("BOTTOM_TRIM", 0.0)
    LEFT_TRIM = env.float("LEFT_TRIM", 0.0)
    RIGHT_TRIM = env.float("RIGHT_TRIM", 0.0)

    # Tapacantos: merma (sobrante de canteadora) aplicada al metraje neto antes de
    # redondear al metro entero que se cobra. 0.10 = +10%.
    EDGE_BANDING_WASTE_FACTOR = env.float("EDGE_BANDING_WASTE_FACTOR", 0.10)

    OPT_RESULT_TTL_SECONDS = env.int("OPT_RESULT_TTL_SECONDS", 259200)

    # Pre-órdenes (cotización mutable): vigencia y tope de abiertas por cliente. Solo
    # siembran la sección "preorders" de la fila singleton de `settings` en su primera
    # lectura; la fuente de verdad en runtime es la tabla `settings` (editable vía
    # PATCH /settings/preorders), igual que los parámetros de corte.
    PREORDER_VALIDITY_DAYS = env.int("PREORDER_VALIDITY_DAYS", 15)
    MAX_OPEN_PREORDERS_PER_CLIENT = env.int("MAX_OPEN_PREORDERS_PER_CLIENT", 5)

    # Base del frontend de Maderable: compone la URL del enlace de revisión que
    # abre el cliente (el origen debe estar también en CORS_ORIGINS). El dashboard
    # usa HashRouter, por eso la base termina en "/#" (ruta = {base}/review/{token}).
    FRONTEND_BASE_URL = env("FRONTEND_BASE_URL", "http://localhost:3001/#")

    # Datos de la empresa (membrete de la proforma). Valores dummy por defecto que
    # solo siembran la fila singleton de `settings` en su primera lectura; la fuente
    # de verdad en runtime es la tabla `settings` (editable vía PATCH /settings/company).
    COMPANY_NAME = env("COMPANY_NAME", "Mi Empresa")
    COMPANY_TAGLINE = env("COMPANY_TAGLINE", "eslogan de la empresa")
    COMPANY_EMAIL = env("COMPANY_EMAIL", "correo@empresa.com")
    COMPANY_PHONE = env("COMPANY_PHONE", "0990000000 / 0990000001")
    COMPANY_BRANCHES = env.json(
        "COMPANY_BRANCHES",
        [
            {"name": "Sucursal 1", "address": "Calle Principal y Secundaria"},
            {"name": "Sucursal 2", "address": "Av. Central y Transversal"},
        ],
    )

    def get_cors_origins(self) -> List[str]:
        """Lista de orígenes permitidos para CORS."""
        return self.CORS_ORIGINS

    def is_development(self) -> bool:
        return self.ENVIRONMENT in ["local", "development"]

    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"


config = Config()
