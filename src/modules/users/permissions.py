"""Per-role authorization matrix (enforcement-phase spec).

Source of truth for which role can access which area. In the enforcement phase, each
route is protected with ``require_role(*RESOURCE_ROLES[key])`` (see ``dependencies.py``).

| Area                          | administrador | vendedor | operador | canteador |
|-------------------------------|---------------|----------|----------|-----------|
| users:manage                  | yes           | no       | no       | no        |
| settings:manage               | yes           | no       | no       | no        |
| branches:manage               | yes           | no       | no       | no        |
| branches:read                 | yes           | yes      | yes      | yes       |
| clients:manage                | yes           | yes      | no       | no        |
| products:write                | yes           | no       | no       | no        |
| products:read                 | yes           | yes      | no       | no        |
| optimizer (optimizations/drafts) | yes        | yes      | no       | no        |
| preorders                     | yes           | yes      | no       | no        |
| orders:write (create/quote)   | yes           | yes      | no       | no        |
| orders:read                   | yes           | yes      | yes      | no        |
| orders:transition (status change) | yes       | yes      | yes*     | yes*      |
| cutting_plan (view plan)      | yes           | yes      | yes      | no        |
| orders:cut (mark pieces)      | yes           | no       | yes      | no        |
| orders:band (edge banding)    | yes           | no       | no       | yes       |
| analytics                     | yes           | no       | no       | no        |

* Per-transition validation lives in TRANSITION_ROLES (orders/model.py). The bander
  only enters ``orders:transition`` to register the dispatch
  (``completed -> despachado``); every other transition stays off-limits there.

The bander doesn't see order detail (no ``orders:read``): only their banding queue
and the start/finish endpoints (``orders:band``).
"""

from src.modules.users.enums import UserRole

_ADMIN = UserRole.ADMIN
_SELLER = UserRole.SELLER
_OPERATOR = UserRole.OPERATOR
_BANDER = UserRole.BANDER

RESOURCE_ROLES: dict[str, tuple[UserRole, ...]] = {
    "users:manage": (_ADMIN,),
    "settings:manage": (_ADMIN,),
    # Branches: only the admin manages them (CRUD). Any staff needs read access
    # to populate selectors and show their branch's name.
    "branches:manage": (_ADMIN,),
    "branches:read": (_ADMIN, _SELLER, _OPERATOR, _BANDER),
    "clients:manage": (_ADMIN, _SELLER),
    "products:write": (_ADMIN,),
    "products:read": (_ADMIN, _SELLER),
    "optimizer": (_ADMIN, _SELLER),
    "preorders": (_ADMIN, _SELLER),
    "orders:write": (_ADMIN, _SELLER),
    "orders:read": (_ADMIN, _SELLER, _OPERATOR),
    "orders:transition": (_ADMIN, _SELLER, _OPERATOR, _BANDER),
    "cutting_plan": (_ADMIN, _SELLER, _OPERATOR),
    "orders:cut": (_ADMIN, _OPERATOR),
    "orders:band": (_ADMIN, _BANDER),
    "analytics": (_ADMIN,),
}
