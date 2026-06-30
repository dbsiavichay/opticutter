# Testing

La suite combina dos capas con propósitos distintos:

| Capa | Marcador | Dónde | Toca PostgreSQL | Para qué |
|------|----------|-------|-----------------|----------|
| **Unitaria** | `unit` | `tests/unit/` | **No** (mock / funciones puras) | Lógica de negocio aislada: máquinas de estado, *gates*, mapeos, cálculos |
| **Integración** | `integration` | `tests/*.py` (resto) | **Sí** (base dedicada `cutter_test_db`) | Endpoints HTTP, queries reales, constraints, flujos end-to-end |

El marcado es **automático por ruta** (hook `pytest_collection_modifyitems` en
`tests/conftest.py`): todo lo que cuelga de `tests/unit/` queda `unit`; el resto,
`integration`. No hace falta anotar a mano.

## Comandos

```bash
# Suite completa (integración + unidad) contra cutter_test_db, con gate de cobertura 80%
make tests            # en Docker
make tests-local      # local (PostgreSQL en localhost:5433)

# Bucle rápido SOLO unitario: sin Postgres, sin gate de cobertura
DATABASE_URL=postgresql://cutter:cutter@localhost:5433/cutter_test_db \
  pytest -m unit --no-cov

# Solo integración
pytest -m integration
```

Notas:

- `pytest -m unit` **no requiere un Postgres vivo**, pero sí que la variable
  `DATABASE_URL` esté **presente** (la lee `src/shared/config.py` al importar). El
  valor puede apuntar a un host inalcanzable: los tests unitarios nunca abren conexión.
- Se usa `--no-cov` en el bucle unitario porque el gate global (`--cov-fail-under=80`,
  en `pyproject.toml`) fallaría sobre un subconjunto. El gate se valida en `make tests`.
- `BCRYPT_ROUNDS=4` lo fija el `Makefile` en los targets de test (hashes bcrypt
  válidos ~16× más rápidos). En dev/prod el default es 12.

## Cómo escribir tests

### Unitario — función pura (sin DB, sin mock)

```python
from src.modules.products.service import ProductService

def test_design_key():
    assert ProductService._design_key("MDP-SL-CSH-15") == "SL-CSH"
```

### Unitario — lógica de servicio con `mock_session`

El fixture `mock_session` (en `tests/unit/conftest.py`) es un `MagicMock(spec=Session)`.
Se construye el servicio con él y se configura por test lo que cada método consulta:

```python
def test_queued_requires_payment(mock_session):
    order = OrderModel(status="confirmed", banding_status="not_applicable")
    svc = OrderService(mock_session)
    svc.get_scoped_or_404 = lambda *a, **k: order   # carga por id → objeto en mano
    with pytest.raises(ValidationError):
        svc.transition(1, OrderStatus.queued, actor=admin, payment=None)
    mock_session.commit.assert_not_called()          # el rechazo no persiste
```

Para consultas: `mock_session.query.return_value.filter.return_value.count.return_value = 2`.

### Integración

Igual que hoy: fixtures `client` (TestClient autenticado como admin) / `anon_client`
/ `db_session` del `tests/conftest.py` raíz. Resérvalo para endpoints, queries reales,
constraints e idempotencia transaccional.

## Regla práctica

- Lógica nueva (validaciones, estados, cálculos) → **test unitario** primero.
- Algo que dependa de una query real, un constraint o un flujo HTTP → **integración**.

### Candidatos de migración a unidad (backlog)

Lógica jugosa que hoy solo se cubre vía integración y se beneficiaría de un test
unitario: hash determinista de la optimización (`OptimizationService._compute_hash`),
resolución de materiales por origen (`MaterialResolver.resolve`), y la expiración /
tope de pre-órdenes (`PreOrderService._expire_if_stale` / `_enforce_open_cap`).
