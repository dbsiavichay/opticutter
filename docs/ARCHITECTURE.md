# Arquitectura del Proyecto Cutter

## Visión General

Cutter es una API FastAPI para optimización de cortes 2D de melamina (algoritmo
guillotina). El código se organiza en **módulos verticales (vertical slices)**: cada
recurso reúne en una sola carpeta su router, su servicio, sus schemas y su modelo ORM.
Esto reduce el boilerplate, mantiene cohesionado todo lo de un recurso y deja el dominio
del algoritmo aislado y libre de frameworks.

El objetivo de diseño es ser **pragmático y fácil de leer**: SOLID donde aporta, sin
ceremonia. No hay repositorios por entidad ni capas de "casos de uso" vacías; el CRUD se
centraliza en una base genérica y los errores en un único handler.

## Estructura

```
src/
├── shared/                 # Núcleo transversal reutilizable
│   ├── config.py           # Config único (lee de entorno; KERF, trims, CORS, DB...)
│   ├── database.py         # Base declarativa, engine, SessionLocal, get_db
│   ├── schemas.py          # CamelModel (contrato camelCase del API)
│   ├── exceptions.py       # AppError + jerarquía con status_code
│   ├── errors.py           # register_exception_handlers(app)
│   └── crud.py             # CRUDService[Model, Create, Update] genérico
├── modules/                # Un slice por recurso
│   ├── clients/            # {model, schemas, service, router}.py
│   ├── products/           # catálogo multi-tipo: + registry.py y types/<tipo>.py
│   ├── orders/             # raíz de agregado: snapshot inmutable + máquina de estados
│   ├── optimizations/      # + proforma.py (PDF) y visualization.py (render)
│   └── system/             # router.py (health + info del servicio)
├── cutting/                # DOMINIO puro del algoritmo (sin frameworks)
│   ├── models.py           # Rectangle, Piece, PlacedPiece, Material, CuttingLayout
│   ├── enums.py            # SplitRule
│   ├── parameters.py       # CuttingParameters (dataclass)
│   └── optimizer.py        # GuillotineOptimizer, MultiSheetGuillotineOptimizer
main.py                     # Crea la app, registra routers + handlers, CORS desde config
alembic/                    # Migraciones (env.py importa Base y los modelos de cada módulo)
```

## Reglas de dependencia

Simples y sin ciclos:

- **`cutting/`** no importa frameworks ni módulos. Permanece puro y testeable de forma
  aislada.
- **`shared/`** no depende de ningún módulo.
- **`modules/*`** dependen de `shared/` y de `cutting/`.
- Dependencias entre módulos solo en una dirección: `optimizations` → `clients`/`products`
  (p. ej. reutiliza `ClientResponse` y `ProductService`; solo optimiza productos tipo
  `board`), nunca al revés.

## Bloques clave

### `shared/crud.py` — base CRUD genérica

`CRUDService[ModelT, CreateT, UpdateT]` centraliza `get`/`get_or_404`/`list`/`create`/
`update`/`delete` y la traducción de `IntegrityError`. Cada servicio solo declara su
`model` y, opcionalmente, `conflict_messages` (substring de la restricción → mensaje
legible) más los métodos específicos del recurso (`search`, `get_by_phone`, ...).

`create` mapea `data.model_dump()` directo a las columnas. Esto elimina los repositorios
por entidad y el CRUD repetido en los servicios.

### `shared/exceptions.py` + `shared/errors.py` — errores centralizados

Una jerarquía con `status_code` propio (`EntityNotFoundError`=404, `ConflictError`=409,
`BusinessRuleError`/`ValidationError`=422; base `AppError`=400). Los servicios y el dominio
lanzan estas excepciones **sin conocer FastAPI**; un único handler registrado en
`register_exception_handlers(app)` las traduce a `{"detail": ...}` con el código correcto.
Así desaparecen los `if not x: raise HTTPException(404)` repetidos en las rutas.

### Inyección con `Depends` + rutas finas

Cada módulo expone un *provider* (p. ej. `client_service(db = Depends(get_db))`). Las rutas
quedan visibles y depurables, sin instanciar servicios a mano ni manejar 404 inline:

```python
@router.get("/{client_id}", response_model=ClientResponse)
def get_client(client_id: int, svc: ClientService = Depends(client_service)):
    return svc.get_or_404(client_id)
```

### `cutting/` — dominio del algoritmo

Dataclasses puras (`Piece`, `Material`, `CuttingLayout`, ...) y los optimizadores
guillotina. El módulo `optimizations` orquesta este dominio y persiste el resultado; si un
requerimiento referencia un tablero inexistente, lanza `EntityNotFoundError` (404) en lugar
de descartarlo en silencio.

## Contrato del API

Todos los schemas extienden `CamelModel`: el contrato externo usa **camelCase** y aceptan
también snake_case en input; internamente se trabaja en snake_case. Las respuestas se
construyen directamente desde los modelos ORM (`from_attributes=True`).

## Base de datos y migraciones

`shared/database.py` define la `Base` declarativa común; todos los modelos ORM la extienden.
`alembic/env.py` apunta a `src.shared.database.Base` e **importa los modelos de cada módulo**
(`src.modules.{clients,products,optimizations,orders}.model`) para poblar `Base.metadata`, de modo
que `alembic revision --autogenerate` detecte las tablas. La URL se toma de
`config.DATABASE_URL`.

## Ejecución y verificación

- **App local**: `make run-local` (`ENVIRONMENT=local python main.py`); SQLite por defecto.
- **Tests**: `make tests-local` (o `.venv/bin/python -m pytest`). La suite cubre el dominio
  del optimizador, el CRUD genérico vía clients/products (incluyendo conflictos 409 y 404),
  el flujo de optimización (geometría) y los documentos comerciales (proforma de
  cotización / orden de pedido), y los endpoints del sistema.
- **Lint**: `make lint-check-local` (ruff).
- **Migraciones**: `alembic upgrade head`; `alembic revision --autogenerate` no debe generar
  diffs cuando los modelos coinciden con el esquema.
