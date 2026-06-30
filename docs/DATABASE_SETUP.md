# Database Setup

Cutter uses SQLAlchemy with Alembic for migrations, against **PostgreSQL
only**. SQLite was used early in the project but has since been removed
entirely — the test suite, local development and production all run against
PostgreSQL so behavior never diverges between environments.

## Initial setup

1. **Install dependencies** (already pinned in `requirements.txt`):
   ```bash
   pip install -r requirements.txt
   ```

2. **Copy environment variables**:
   ```bash
   cp .env.example .env
   ```

3. **Provide PostgreSQL**:
   - **Docker (recommended)**: `docker-compose.yml` already defines a
     `postgres` service (database `cutter_db`, user/password `cutter`,
     exposed on host port `5433`). `make dev` / `docker compose up -d`
     starts it automatically.
   - **Local PostgreSQL**: point `DATABASE_URL` at your own instance, e.g.:
     ```
     DATABASE_URL=postgresql://cutter:cutter@localhost:5433/cutter_db
     ```

There is no default value for `DATABASE_URL` — `src/shared/config.py` reads
it directly from the environment and fails fast if it's missing, by design.

## File layout

- `src/shared/database.py` — SQLAlchemy setup (`Base`, `engine`,
  `SessionLocal`, `get_db`).
- `src/modules/<resource>/model.py` — ORM models per module (e.g.
  `src/modules/products/model.py`).
- `alembic/` — Alembic configuration and migrations
  (`alembic/env.py` imports `Base` and every module's models).
- `alembic.ini` — Alembic configuration file.

## Alembic workflow

### Generate a migration after changing models

```bash
make migrations m="add half-board support"
# equivalent to: alembic revision --autogenerate -m "add half-board support"
```

### Apply pending migrations

```bash
make upgrade
# equivalent to: alembic upgrade head
```

### Revert the last migration

```bash
make downgrade d=-1
# equivalent to: alembic downgrade -1
```

### Inspect history

```bash
alembic history
```

## Adding a new model

1. Define the model in its module, inheriting from `Base` (e.g.
   `src/modules/clients/model.py`).
2. Register it for autogeneration by importing it in `alembic/env.py`
   alongside the other modules:
   ```python
   from src.modules.clients.model import ClientModel  # noqa: F401
   from src.shared.database import Base
   ```
3. Generate and apply the migration:
   ```bash
   make migrations m="add Client model"
   make upgrade
   ```

`alembic revision --autogenerate` should produce **no diff** when every
model is already reflected in the schema — treat a non-empty autogenerate as
a signal that a model and a migration drifted apart.

## Using the database in FastAPI

```python
from fastapi import Depends
from sqlalchemy.orm import Session
from src.shared.database import get_db

@app.get("/example")
def get_data(db: Session = Depends(get_db)):
    ...
```

## Test database

Integration tests run against a **separate** database, `cutter_test_db`, so
the suite's per-test `TRUNCATE ... RESTART IDENTITY CASCADE` never touches
development data. See [`TESTING.md`](TESTING.md) for the full setup and the
unit-test fast loop that doesn't need PostgreSQL at all.
