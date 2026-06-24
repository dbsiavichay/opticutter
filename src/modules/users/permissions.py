"""Matriz de autorización por rol (spec de la fase de enforcement).

Fuente de verdad de qué rol puede acceder a qué área. En la fase de enforcement, cada
ruta se protege con ``require_role(*RESOURCE_ROLES[clave])`` (ver ``dependencies.py``).

| Área                          | administrador | vendedor | operador | canteador |
|-------------------------------|---------------|----------|----------|-----------|
| users:manage                  | sí            | no       | no       | no        |
| settings:manage               | sí            | no       | no       | no        |
| branches:manage               | sí            | no       | no       | no        |
| branches:read                 | sí            | sí       | sí       | sí        |
| clients:manage                | sí            | sí       | no       | no        |
| products:write                | sí            | no       | no       | no        |
| products:read                 | sí            | sí       | no       | no        |
| optimizer (optimizations/drafts) | sí         | sí       | no       | no        |
| preorders                     | sí            | sí       | no       | no        |
| orders:write (crear/cotizar)  | sí            | sí       | no       | no        |
| orders:read                   | sí            | sí       | sí       | no        |
| orders:transition (cambiar estado) | sí       | sí       | sí*      | no        |
| cutting_plan (ver plan)       | sí            | sí       | sí       | no        |
| orders:cut (marcar piezas)    | sí            | no       | sí       | no        |
| orders:band (canteado)        | sí            | no       | no       | sí        |
| analytics                     | sí            | no       | no       | no        |

* La validación por transición específica vive en TRANSITION_ROLES (orders/model.py).

El canteador no ve el detalle de la orden (sin ``orders:read``): solo su cola de
canteado y los endpoints de inicio/fin (``orders:band``).
"""

from src.modules.users.enums import UserRole

_ADMIN = UserRole.ADMIN
_SELLER = UserRole.SELLER
_OPERATOR = UserRole.OPERATOR
_BANDER = UserRole.BANDER

RESOURCE_ROLES: dict[str, tuple[UserRole, ...]] = {
    "users:manage": (_ADMIN,),
    "settings:manage": (_ADMIN,),
    # Sucursales: solo el admin las administra (CRUD). La lectura la necesita
    # cualquier staff para poblar selectores y mostrar el nombre de su sucursal.
    "branches:manage": (_ADMIN,),
    "branches:read": (_ADMIN, _SELLER, _OPERATOR, _BANDER),
    "clients:manage": (_ADMIN, _SELLER),
    "products:write": (_ADMIN,),
    "products:read": (_ADMIN, _SELLER),
    "optimizer": (_ADMIN, _SELLER),
    "preorders": (_ADMIN, _SELLER),
    "orders:write": (_ADMIN, _SELLER),
    "orders:read": (_ADMIN, _SELLER, _OPERATOR),
    "orders:transition": (_ADMIN, _SELLER, _OPERATOR),
    "cutting_plan": (_ADMIN, _SELLER, _OPERATOR),
    "orders:cut": (_ADMIN, _OPERATOR),
    "orders:band": (_ADMIN, _BANDER),
    "analytics": (_ADMIN,),
}
