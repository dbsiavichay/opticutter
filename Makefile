# Makefile generated with pymakefile
help:
	@grep -E '^[A-Za-z0-9_.-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "[36m%-30s[0m %s\n", $$1, $$2}'

build:  ## Build the docker image
	docker compose build

start:
	docker compose up -d

dev: 
	docker compose up -d && docker rm -f api && docker compose run --rm -p 3000:3000 api

down:  ## Stop the docker containers
	docker compose down

tests:  ## Run tests
	docker compose run --no-deps --rm api pytest --cov='app'

lint-fix:  ## Fix linter errors
	black . && isort . --profile black && flake8 .	

lint-check:  ## Run linter
	docker-compose run --no-deps --rm api black . --check
	docker-compose run --no-deps --rm api isort . --check-only --profile black
	docker-compose run --no-deps --rm api flake8 .
