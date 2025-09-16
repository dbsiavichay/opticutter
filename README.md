# Cutter API

API REST en Python + FastAPI para optimizar cortes 2D de tableros de melamina minimizando desperdicio y costos. Incluye caché en Redis e infraestructura con Docker y docker-compose.

Contenido:
- Endpoints: POST /api/v1/optimize, GET /api/v1/optimize/by-hash/{hash}, GET /api/v1/optimize/recent
- Health: GET /api/v1/health/, GET /api/v1/health/ready, Root / y /health
- Algoritmo: Guillotine 2D first-fit decreasing, respeta kerf y trims, reutiliza residuos (free rectangles)
- Cacheo: Redis con clave opt:{sha256(payload_canónico)} y TTL configurable

Requisitos:
- Docker y docker-compose

Uso rápido:
1) Copiar variables de entorno

    cp .env.example .env

2) Construir e iniciar

    docker compose up -d --build

3) Abrir docs

    http://localhost:3000/docs

Ejemplo de petición:

POST /api/v1/optimize
{
  "cuts": [...],
  "materials": [...],
  "cutting_parameters": {"kerf": 5, "top_trim": 0, "bottom_trim": 0, "left_trim": 0, "right_trim": 0}
}

Notas:
- Si Redis no está disponible, el servicio sigue operando pero sin cacheo.
- El algoritmo es heurístico y prioriza simplicidad/rapidez. Puede mejorarse con OR-Tools en versiones futuras.
