# syntax=docker/dockerfile:1

# ---- Stage 1: builder ----
# Compila las dependencias de producción dentro de un virtualenv aislado.
FROM python:3.11-slim-bookworm AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Toolchain de compilación solo en el builder (no llega a la imagen final).
RUN apt-get update -y && \
    apt-get install -y --no-install-recommends build-essential && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Virtualenv que copiaremos a los stages siguientes.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /src

COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# ---- Stage 2: dev ----
# Imagen para desarrollo/tests: añade ruff, pytest, etc. sobre el venv.
# docker-compose construye este target (build.target: dev).
# requirements.txt ya quedó en /src desde el builder, así que el
# "-r requirements.txt" de requirements_dev.txt resuelve correctamente.
FROM builder AS dev

ENV PYTHONUNBUFFERED=1

COPY requirements_dev.txt .
RUN pip install -r requirements_dev.txt

EXPOSE 3000

# Sobreescrito por docker-compose con --reload; aquí queda un default sensato.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "3000", "--reload"]

# ---- Stage 3: runtime (producción, target por defecto) ----
FROM python:3.11-slim-bookworm AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /src

# Copia el virtualenv ya construido (solo deps de producción, sin toolchain).
COPY --from=builder /opt/venv /opt/venv

# Usuario sin privilegios.
RUN useradd --create-home --uid 1000 appuser

COPY . .
RUN chown -R appuser:appuser /src

USER appuser

EXPOSE 3000

# Comando de producción (sin --reload).
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "3000"]
