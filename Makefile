# Makefile para Cutter API
.PHONY: help build start dev down tests lint-fix lint-check install clean logs redis-cli

help: ## Muestra esta ayuda
	@grep -E '^[A-Za-z0-9_.-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

install: ## Instala las dependencias
	pip install -r requirements_dev.txt

build: ## Construye la imagen Docker
	docker compose build

start: ## Inicia los contenedores en modo daemon
	docker compose up -d

dev: ## Inicia en modo desarrollo con recarga automática
	docker compose up -d && docker rm -f api || true && docker compose run --rm -e ENVIRONMENT=local -p 3000:3000 api

down: ## Detiene los contenedores
	docker compose down

logs: ## Muestra los logs de la aplicación
	docker compose logs -f api

tests: ## Ejecuta las pruebas
	docker compose run --no-deps --rm api pytest -q

tests-local: ## Ejecuta las pruebas localmente (requiere PostgreSQL en localhost:5433)
	DATABASE_URL=postgresql://cutter:cutter@localhost:5433/cutter_db pytest -q

lint-fix: ## Corrige errores de formato y lint
	source .venv/bin/activate && ruff check --fix . && ruff format .

lint-check: ## Verifica el formato del código
	docker compose run --no-deps --rm api ruff check .
	docker compose run --no-deps --rm api ruff format --check .

lint-check-local: ## Verifica el formato del código localmente
	ruff check . && ruff format --check .

clean: ## Limpia contenedores e imágenes no utilizadas
	docker system prune -f
	docker volume prune -f

shell: ## Abre una shell en el contenedor
	docker compose run --rm api bash

redis-cli: ## Abre redis-cli dentro del contenedor de Redis
	docker exec -it redis redis-cli

run-local: ## Ejecuta la aplicación localmente (requiere PostgreSQL en localhost:5433)
	ENVIRONMENT=local DATABASE_URL=postgresql://cutter:cutter@localhost:5433/cutter_db python main.py

seed-local: ## Siembra tableros y tapacantos en PostgreSQL local (puerto 5433)
	DATABASE_URL=postgresql://cutter:cutter@localhost:5433/cutter_db .venv/bin/python scripts/seed_boards.py

seed-admin: ## Crea el primer administrador desde ADMIN_EMAIL/ADMIN_PASSWORD en .env
	.venv/bin/python scripts/seed_admin.py

seed-demo: ## Siembra datos demo (sucursales/usuarios/clientes/pre-órdenes/órdenes por estado) en PostgreSQL local (5433). Usa reset=1 para regenerar.
	DATABASE_URL=postgresql://cutter:cutter@localhost:5433/cutter_db REDIS_URL=redis://localhost:6379/0 .venv/bin/python scripts/seed_demo.py $(if $(reset),--reset)

setup: ## Configuración inicial del proyecto
	cp .env.example .env || true
	@echo "Archivo .env creado. Edítalo según tus necesidades."

migrations:  ## Create a new migration with Alembic
	docker compose run --no-deps --rm api alembic revision --autogenerate -m "$(m)"

upgrade:  ## Apply all pending migrations with Alembic
	docker compose run --no-deps --rm api alembic upgrade head

downgrade:  ## Downgrade the database to the previous migration
	docker compose run --no-deps --rm api alembic downgrade $(d)