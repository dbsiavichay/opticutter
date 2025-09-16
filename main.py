import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from config import config
from src.api.boards import router as boards_router
from src.api.clients import router as clients_router
from src.api.cutter import router as cutter_router
from src.api.health import router as health_router
from src.api.optimize import router as optimize_router
from src.services.optimization import cache

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
    # could test redis connection here
    try:
        await cache._redis.ping()
        logger.info("Redis conectado correctamente")
    except Exception as e:
        logger.warning(f"No se pudo conectar a Redis en startup: {e}")
    yield
    logger.info("Cerrando aplicación FastAPI")
    try:
        await cache.close()
    except Exception:
        pass


# Configuración de CORS
origins = [
    "http://localhost:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3001",
]

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
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
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
