import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from config import config
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
    description="API para el sistema Cutter de Maderable",
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
app.add_middleware(ErrorHandlingMiddleware)

# Incluir rutas
app.include_router(api_router, prefix="/api/v1")


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
        host="0.0.0.0",
        port=3000,
        reload=True if config.ENVIRONMENT == "local" else False,
        log_level=config.LOG_LEVEL.lower(),
    )
