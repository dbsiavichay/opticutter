import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from src.api.v1.routes import (
    boards_router,
    clients_router,
    cutter_router,
    health_router,
    optimize_router,
)
from src.shared.config import config
from src.shared.errors import register_exception_handlers

# Configurar logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manejo del ciclo de vida de la aplicación"""
    logger.info("Iniciando aplicación FastAPI")
    yield
    logger.info("Cerrando aplicación FastAPI")


# Crear aplicación FastAPI
app = FastAPI(
    title="Cutter API",
    description="API para optimización de cortes de melamina",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Middlewares
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Manejo centralizado de errores de aplicación
register_exception_handlers(app)

# Incluir rutas
app.include_router(health_router, prefix="/api/v1")
app.include_router(boards_router, prefix="/api/v1")
app.include_router(clients_router, prefix="/api/v1")
app.include_router(cutter_router, prefix="/api/v1")
app.include_router(optimize_router, prefix="/api/v1")


@app.get("/")
async def root():
    """Redirige a la documentación de la API"""
    return RedirectResponse("/docs")


@app.get("/health")
async def health_check():
    """Endpoint de verificación de salud"""
    return {"status": "healthy", "environment": config.ENVIRONMENT, "version": "1.0.0"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=config.HOST,
        port=config.PORT,
        reload=True if config.ENVIRONMENT == "local" else False,
        log_level=config.LOG_LEVEL.lower(),
    )
