# Multi-sucursal — contrato de API

Cutter ahora aísla **órdenes, pre-órdenes y borradores** por sucursal. Este documento
resume lo que cambia para el frontend (dashboard React). Detalle de auth en
[`AUTH.md`](AUTH.md).

## Modelo

- **Sucursal (`branch`)** es una entidad real (`/branches`). Reemplaza al JSON de
  membrete que vivía en `settings.company_branches`.
- Cada **usuario** staff (`vendedor`/`operador`) está atado a **una** sucursal
  (`branchId`). El **administrador** es global (`branchId` nulo): ve y opera todas.
- **Órdenes, pre-órdenes y borradores** guardan su `branchId`. Es un hecho histórico:
  reasignar la sucursal de un usuario **no** mueve sus documentos previos. Sus
  respuestas (detalle y listado) **incrustan** la sucursal dueña como un objeto
  compacto `branch: { id, code, name }`, para que el dashboard pueda mostrar la columna
  "Sucursal" sin una llamada extra.
- **Clientes y productos siguen siendo globales** (una sola cartera / catálogo).

## Aislamiento (qué ve/hace cada quién)

| Rol | Listados y acceso | Crear |
|-----|-------------------|-------|
| `administrador` | **Todas** las sucursales; filtro opcional `?branchId=` | Debe indicar `branchId` |
| `vendedor`/`operador` | Solo **su** sucursal | Hereda su sucursal (el `branchId` del body se ignora) |

Un recurso de otra sucursal devuelve **404** (no 403): no se revela que existe.

## Endpoints nuevos

### `/branches` (CRUD, solo admin escribe; cualquier staff lee)
- `POST /api/v1/branches` — `{ code, name, address?, phone? }`
- `GET /api/v1/branches` — paginado, `?search=`
- `GET /api/v1/branches/{id}`
- `PUT /api/v1/branches/{id}` — incluye `isActive` (baja lógica)
- `DELETE /api/v1/branches/{id}`

### Analítica por sucursal (admin)
- `GET /api/v1/analytics/breakdown/branch` — comparativo (conteo + ingreso) por almacén.
- Todos los endpoints de analytics aceptan `?branchId=` para acotar a una sucursal.

## Cambios en endpoints existentes

- **Usuarios** (`POST/PUT /users`, respuesta de login): el body/objeto `user` incluye
  `branchId`. Obligatorio para `vendedor`/`operador`; ignorado para `administrador`
  (queda nulo). Mostrar un selector de sucursal en el alta/edición de staff.
- **Pre-órdenes** (`POST /preorders`): acepta `branchId`. El staff puede omitirlo
  (hereda el suyo); el admin debe enviarlo. `GET /preorders` acepta `?branchId=` (admin).
- **Órdenes** (`GET /orders`): acepta `?branchId=` (admin). La orden nace con la
  sucursal de la pre-orden al confirmar; su proforma/hoja de producción muestran esa
  sucursal en el membrete.
- **Borradores** (`POST /optimization-drafts`): acepta `branchId` (mismo criterio que
  pre-órdenes); `GET` acepta `?branchId=` (admin).

## Errores relevantes

- `422 VALIDATION_ERROR` (`field: "branchId"`): admin creando sin indicar sucursal, o
  sucursal inactiva.
- `403 FORBIDDEN`: staff sin sucursal asignada (estado inválido a corregir por el admin).
- `404 NOT_FOUND`: acceso a un recurso de otra sucursal (uniforme con "no existe").
