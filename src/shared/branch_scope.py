"""Branch isolation at the service level (generic infrastructure).

The *branch scope* expresses which rows a user can see/touch:

- ``None`` → global role (administrador or vendedor): sees and operates on
  **all** branches (no filter).
- ``int``  → operador bound to that branch: only sees/operates on their own.

Resolved once per request (``users.dependencies.get_branch_scope``) and
propagated to the services. This mixin centralizes the listing filter and the
ownership check so it isn't repeated — or leaked — in every service. It's
orthogonal to ``require_permission`` (role → *which actions*); the scope
decides *which rows*.

No import from any domain module: it operates on ``self.model`` (which must
have a ``branch_id`` column) and ``self.get_or_404``, same as ``CRUDService``.
"""

from typing import Optional

from sqlalchemy.orm import Query

from src.shared.exceptions import EntityNotFoundError


class BranchScopedMixin:
    """Branch filter and ownership guard for services with ``branch_id``.

    The subclass defines ``model`` (the ORM model with ``branch_id``) and
    provides ``get_or_404`` (via ``CRUDService`` or its own).
    """

    model = None  # type: ignore[assignment]

    def _apply_branch_scope(
        self,
        query: Query,
        branch_scope: Optional[int],
        branch_filter: Optional[int] = None,
    ) -> Query:
        """Applies isolation to a listing.

        - scoped (``branch_scope`` not None, e.g. operador): locked to their branch.
        - global (``branch_scope`` None, admin/vendedor): no filter, unless it asks
          to narrow to a specific branch via ``branch_filter``.
        """
        if branch_scope is not None:
            return query.filter(self.model.branch_id == branch_scope)
        if branch_filter is not None:
            return query.filter(self.model.branch_id == branch_filter)
        return query

    def get_scoped_or_404(self, id: int, branch_scope: Optional[int]):
        """Gets by id verifying it belongs to the user's branch.

        A resource from another branch returns a **uniform 404** (not 403): it
        doesn't reveal that it exists, same as the public review links.
        """
        obj = self.get_or_404(id)
        if branch_scope is not None and obj.branch_id != branch_scope:
            raise EntityNotFoundError(self.model.__name__, id)
        return obj
