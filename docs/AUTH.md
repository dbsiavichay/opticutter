# Autenticación y autorización (RBAC)

Contrato de auth del API Cutter para el dashboard web (React). Todos los endpoints
salvo los públicos exigen un **access token** (JWT) en el header
`Authorization: Bearer <accessToken>`. La autorización es por **rol** según la
matriz de permisos.

## Roles

| Rol (valor en BD)    | Descripción                                  |
|----------------------|----------------------------------------------|
| `administrador`      | Acceso total (gestión, config, analítica).   |
| `vendedor`           | Comercial: catálogo (lectura), clientes, optimizador, pre-órdenes, órdenes. |
| `operador`           | Taller (corte): lectura de órdenes, plan de corte y marcado de piezas. |
| `canteador`          | Taller (canteado): su cola de canteado e inicio/fin del tapacanto; **no** ve el detalle de la orden. |

`operador` y `canteador` son roles de taller atados a una sucursal; `administrador` y
`vendedor` son globales.

El login es por `email` (único). La contraseña se guarda solo como hash bcrypt.

## Flujo de sesión

1. **Login** → `POST /api/v1/auth/login` con `{ email, password }`.
   Respuesta: `{ accessToken, refreshToken, tokenType: "bearer", expiresIn, user }`.
   - `accessToken`: JWT corto (por defecto 30 min, `ACCESS_TOKEN_EXPIRE_MINUTES`).
   - `refreshToken`: token opaco largo (por defecto 30 días, `REFRESH_TOKEN_EXPIRE_DAYS`).
   - `expiresIn`: vigencia del access token en segundos.
2. **Usar el API** → enviar `Authorization: Bearer <accessToken>` en cada request.
3. **Renovar** → cuando el access token expira (o ante un `401`), llamar
   `POST /api/v1/auth/refresh` con `{ refreshToken }`. Devuelve un **par nuevo**
   (mismo shape que login). El refresh presentado **se rota**: queda invalidado y se
   emite otro. Guardar siempre el `refreshToken` más reciente.
4. **Cerrar sesión** → `POST /api/v1/auth/logout` con `{ refreshToken }` (revoca ese
   refresh; idempotente, `204`).

### Seguridad del refresh token (rotación y reúso)

- Cada `refreshToken` se usa **una sola vez**: `refresh` lo revoca y entrega uno nuevo.
- Si se reusa un refresh **ya rotado** (señal de robo), el API revoca **toda la
  familia** de refresh tokens del usuario y responde `401`. El usuario debe
  volver a hacer login. → El front nunca debe reusar un refresh viejo; debe
  reemplazarlo por el que devuelve `refresh`.
- En reposo solo se guarda el `sha256` del token, nunca el token en claro.

## Autoservicio (cualquier rol autenticado)

- `GET /api/v1/auth/me` → usuario autenticado.
- `PATCH /api/v1/auth/me` con `{ fullName }` → edita **solo** el nombre propio.
  No permite cambiar `role`, `isActive` ni `email` (eso es gestión solo-admin).
- `POST /api/v1/auth/change-password` con `{ currentPassword, newPassword }` → cambia
  la propia contraseña verificando la actual. **Revoca todos los refresh tokens** del
  usuario (cierra otras sesiones); el front debe re-loguear tras un `204`.

## Semántica de errores

| Código | Significado | Acción del front |
|--------|-------------|------------------|
| `401 UNAUTHORIZED` | Falta el token, es inválido o expiró; o credenciales malas. | Intentar `refresh`; si también `401`, redirigir a login. |
| `403 FORBIDDEN`    | Autenticado pero el **rol** no tiene permiso para esa área. | Mostrar "sin permiso"; no reintentar. |

Todos los errores comparten la envoltura `{ errors: [{ code, message, field? }], meta }`.

## Matriz de permisos por endpoint

Fuente de verdad: `src/modules/users/permissions.py` (`RESOURCE_ROLES`). Cada ruta
se protege con `Depends(require_permission("<clave>"))`.

| Área (`clave`)        | administrador | vendedor | operador | canteador | Endpoints |
|-----------------------|:---:|:---:|:---:|:---:|---|
| `users:manage`        | ✅ | ❌ | ❌ | ❌ | `/users/*` |
| `settings:manage`     | ✅ | ❌ | ❌ | ❌ | `/settings/*` |
| `analytics`           | ✅ | ❌ | ❌ | ❌ | `/analytics/*` |
| `products:read`       | ✅ | ✅ | ❌ | ❌ | `GET /products/*` |
| `products:write`      | ✅ | ❌ | ❌ | ❌ | `POST/PUT/DELETE /products/*` |
| `clients:manage`      | ✅ | ✅ | ❌ | ❌ | `/clients/*` |
| `optimizer`           | ✅ | ✅ | ❌ | ❌ | `/optimize/*`, `/optimization-drafts/*` |
| `preorders`           | ✅ | ✅ | ❌ | ❌ | `/preorders/*` (interno) |
| `orders:read`         | ✅ | ✅ | ✅ | ❌ | `GET /orders`, `GET /orders/{id}`, `GET /orders/{id}/proforma` |
| `orders:write`        | ✅ | ✅ | ❌ | ❌ | `POST /orders/{id}/invoice`, `GET /orders/{id}/export` |
| `orders:transition`   | ✅ | ✅ | ✅* | ❌ | `PATCH /orders/{id}/status` (filtra por transición en `TRANSITION_ROLES`) |
| `cutting_plan`        | ✅ | ✅ | ✅ | ❌ | `GET /orders/{id}/cutting-plan`, `GET /orders/{id}/production-sheet` |
| `orders:cut`          | ✅ | ❌ | ✅ | ❌ | `PATCH /orders/{id}/cutting-plan/pieces/{id}` |
| `orders:band`         | ✅ | ❌ | ❌ | ✅ | `GET /orders/banding-queue`, `PATCH /orders/{id}/banding` |

\* `orders:transition` es la puerta gruesa; qué rol puede cada transición concreta
vive en `TRANSITION_ROLES` (`src/modules/orders/model.py`).

## Endpoints públicos (sin token)

- `GET /health`, `GET /api/v1/health/`, `/health/ready`, `/api/v1/cutter/*` — diagnóstico.
- `POST /api/v1/auth/login`, `POST /api/v1/auth/refresh`, `POST /api/v1/auth/logout`.
- `GET/POST /api/v1/public/review/{token}*` — flujo de revisión del cliente:
  el **token del enlace** es la única credencial (no usa JWT).

## Configuración (env)

| Var | Default | Descripción |
|-----|---------|-------------|
| `SECRET_KEY` | `dev-secret-change-me` (obligatorio en prod) | Firma HS256 del JWT. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Vigencia del access token. |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `30` | Vigencia del refresh token. |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | vacío | Siembran el primer admin (migración idempotente). |
