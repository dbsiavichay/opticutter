"""Aislamiento por sucursal a nivel de servicio (infraestructura genérica).

El *branch scope* expresa qué filas puede ver/tocar un usuario:

- ``None`` → administrador global: ve y opera **todas** las sucursales (sin filtro).
- ``int``  → staff atado a esa sucursal: solo ve/opera la suya.

Se resuelve una vez por request (``users.dependencies.get_branch_scope``) y se
propaga a los servicios. Este mixin centraliza el filtro de listado y la verificación
de pertenencia para no repetirlo —ni arriesgar fugas— en cada servicio. Es ortogonal
a ``require_permission`` (rol → *qué acciones*); el scope decide *qué filas*.

Sin import de ningún módulo de dominio: opera sobre ``self.model`` (que debe tener
una columna ``branch_id``) y ``self.get_or_404``, igual que ``CRUDService``.
"""

from typing import Optional

from sqlalchemy.orm import Query

from src.shared.exceptions import EntityNotFoundError


class BranchScopedMixin:
    """Filtro y guardia de pertenencia por sucursal para servicios con ``branch_id``.

    La subclase define ``model`` (el modelo ORM con ``branch_id``) y aporta
    ``get_or_404`` (vía ``CRUDService`` o propio).
    """

    model = None  # type: ignore[assignment]

    def _apply_branch_scope(
        self,
        query: Query,
        branch_scope: Optional[int],
        branch_filter: Optional[int] = None,
    ) -> Query:
        """Aplica el aislamiento a un listado.

        - staff (``branch_scope`` no None): bloqueado a su sucursal.
        - admin (``branch_scope`` None): sin filtro, salvo que pida estrechar a una
          sucursal concreta con ``branch_filter``.
        """
        if branch_scope is not None:
            return query.filter(self.model.branch_id == branch_scope)
        if branch_filter is not None:
            return query.filter(self.model.branch_id == branch_filter)
        return query

    def get_scoped_or_404(self, id: int, branch_scope: Optional[int]):
        """Obtiene por id verificando que pertenezca a la sucursal del usuario.

        Un recurso de otra sucursal devuelve **404 uniforme** (no 403): no se revela
        que existe, igual que los enlaces de revisión públicos.
        """
        obj = self.get_or_404(id)
        if branch_scope is not None and obj.branch_id != branch_scope:
            raise EntityNotFoundError(self.model.__name__, id)
        return obj
