# Makefile para Cutter API
.PHONY: help build start dev down tests lint-fix lint-check install clean logs redis-cli autoflake-fix autoflake-check

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

tests-local: ## Ejecuta las pruebas localmente
	pytest -q

lint-fix: ## Corrige errores de formato
	source .venv/bin/activate && autoflake . && black . && isort . --profile black && flake8 .

lint-check: ## Verifica el formato del código
	docker compose run --no-deps --rm api autoflake . --check
	docker compose run --no-deps --rm api black . --check
	docker compose run --no-deps --rm api isort . --check-only --profile black
	docker compose run --no-deps --rm api flake8 .

lint-check-local: ## Verifica el formato del código localmente
	autoflake . --check && black . --check && isort . --check-only --profile black && flake8 .

autoflake-fix: ## Elimina imports no usados y variables no utilizadas
	autoflake .

autoflake-check: ## Verifica imports no usados sin hacer cambios
	autoflake . --check

clean: ## Limpia contenedores e imágenes no utilizadas
	docker system prune -f
	docker volume prune -f

shell: ## Abre una shell en el contenedor
	docker compose run --rm api bash

redis-cli: ## Abre redis-cli dentro del contenedor de Redis
	docker exec -it redis redis-cli

run-local: ## Ejecuta la aplicación localmente
	ENVIRONMENT=local python main.py

setup: ## Configuración inicial del proyecto
	cp .env.example .env || true
	@echo "Archivo .env creado. Edítalo según tus necesidades."

migrations:  ## Create a new migration with Alembic
	docker compose run --no-deps --rm api alembic revision --autogenerate -m "$(m)"

upgrade:  ## Apply all pending migrations with Alembic
	docker compose run --no-deps --rm api alembic upgrade head

downgrade:  ## Downgrade the database to the previous migration
	docker compose run --no-deps --rm api alembic downgrade $(d)