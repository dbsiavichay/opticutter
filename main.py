import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from config import config
from src.certificate.infra.routers import router as certificate_router
from src.core.infra.adapters import OpenTelemetry
from src.core.infra.middlewares import ErrorHandlingMiddleware
from src.sealer.infra.routers import router as sealer_router

logging.basicConfig(level=logging.INFO, format="%(levelname)s:     %(message)s")

telemetry = OpenTelemetry()

origins = ["http://localhost:3000"]

app = FastAPI()
telemetry.instrument(app, config=config.get_otel_config())


app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(ErrorHandlingMiddleware)

app.include_router(certificate_router, prefix="/api/certificates")
app.include_router(sealer_router, prefix="/api/certificates")


@app.get("/")
async def root():
    return RedirectResponse("/docs")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=3000)
