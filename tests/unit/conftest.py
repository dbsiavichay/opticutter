"""Fixtures de la capa de tests UNITARIOS (sin base de datos).

Todo lo que cuelga de ``tests/unit/`` se marca ``unit`` automáticamente (hook
``pytest_collection_modifyitems`` en ``tests/conftest.py``) y **no** abre conexión a
PostgreSQL: el fixture ``_create_schema`` ya no es ``autouse``, así que solo los
tests que piden ``db_session`` (los de integración) tocan la base.

Patrones de prueba sin DB:

- **Funciones puras**: se ejercen directo (p. ej. ``hash_token``, ``_design_key``,
  ``_has_payment``, ``_progress``).
- **Lógica de servicio**: se construye el servicio con ``mock_session`` y se
  configura por test lo que cada método consulta::

      mock_session.get.return_value = some_model
      mock_session.query.return_value.filter.return_value.count.return_value = 3

  Para la carga por id con aislamiento por sucursal (``get_scoped_or_404``) lo más
  limpio es reemplazar el método en la instancia: ``svc.get_scoped_or_404 = lambda
  *a, **k: order``.
"""

from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session


@pytest.fixture
def mock_session():
    """Doble de ``sqlalchemy.orm.Session`` para aislar la lógica de la persistencia.

    ``spec=Session`` limita la superficie a la interfaz real de la sesión (``get``,
    ``query``, ``add``, ``commit``, ``refresh``, ``flush``, ``delete``), así un typo
    en un método inexistente falla en vez de pasar silencioso.
    """
    return MagicMock(spec=Session)
