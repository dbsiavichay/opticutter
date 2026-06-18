"""Matriz de autorización por rol (spec de la fase de enforcement).

Fuente de verdad de qué rol puede acceder a qué área. En la fase de enforcement, cada
ruta se protege con ``require_role(*RESOURCE_ROLES[clave])`` (ver ``dependencies.py``).

| Área                          | administrador | vendedor | operador |
|-------------------------------|---------------|----------|----------|
| users:manage                  | sí            | no       | no       |
| settings:manage               | sí            | no       | no       |
| branches:manage               | sí            | no       | no       |
| branches:read                 | sí            | sí       | sí       |
| clients:manage                | sí            | sí       | no       |
| products:write                | sí            | no       | no       |
| products:read                 | sí            | sí       | no       |
| optimizer (optimizations/drafts) | sí         | sí       | no       |
| preorders                     | sí            | sí       | no       |
| orders:write (crear/cotizar)  | sí            | sí       | no       |
| orders:read                   | sí            | sí       | sí       |
| orders:transition (cambiar estado) | sí       | sí       | sí*      |
| cutting_plan (ver plan)       | sí            | sí       | sí       |
| orders:cut (marcar piezas)    | sí            | no       | sí       |
| analytics                     | sí            | no       | no       |

* La validación por transición específica vive en TRANSITION_ROLES (orders/model.py).
"""

from src.modules.users.enums import UserRole

_ADMIN = UserRole.ADMIN
_SELLER = UserRole.SELLER
_OPERATOR = UserRole.OPERATOR

RESOURCE_ROLES: dict[str, tuple[UserRole, ...]] = {
    "users:manage": (_ADMIN,),
    "settings:manage": (_ADMIN,),
    # Sucursales: solo el admin las administra (CRUD). La lectura la necesita
    # cualquier staff para poblar selectores y mostrar el nombre de su sucursal.
    "branches:manage": (_ADMIN,),
    "branches:read": (_ADMIN, _SELLER, _OPERATOR),
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
    "analytics": (_ADMIN,),
}
