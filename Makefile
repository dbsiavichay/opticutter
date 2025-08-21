# Makefile para Cutter API
.PHONY: help build start dev down tests lint-fix lint-check install clean logs

help: ## Muestra esta ayuda
	@grep -E '^[A-Za-z0-9_.-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

install: ## Instala las dependencias
	pip install -r requirements_dev.txt

build: ## Construye la imagen Docker
	docker compose build

start: ## Inicia los contenedores en modo daemon
	docker compose up -d

dev: ## Inicia en modo desarrollo con recarga automática
	docker compose up -d && docker rm -f api && docker compose run --rm -p 3000:3000 api

down: ## Detiene los contenedores
	docker compose down

logs: ## Muestra los logs de la aplicación
	docker compose logs -f api

tests: ## Ejecuta las pruebas
	docker compose run --no-deps --rm api pytest --cov=src tests/

tests-local: ## Ejecuta las pruebas localmente
	pytest --cov=src tests/

lint-fix: ## Corrige errores de formato
	black . && isort . --profile black && flake8 .

lint-check: ## Verifica el formato del código
	docker compose run --no-deps --rm api black . --check
	docker compose run --no-deps --rm api isort . --check-only --profile black
	docker compose run --no-deps --rm api flake8 .

lint-check-local: ## Verifica el formato del código localmente
	black . --check && isort . --check-only --profile black && flake8 .

clean: ## Limpia contenedores e imágenes no utilizadas
	docker system prune -f
	docker volume prune -f

shell: ## Abre una shell en el contenedor
	docker compose run --rm api bash

run-local: ## Ejecuta la aplicación localmente
	python main.py

setup: ## Configuración inicial del proyecto
	cp .env.example .env
	@echo "Archivo .env creado. Edítalo según tus necesidades."