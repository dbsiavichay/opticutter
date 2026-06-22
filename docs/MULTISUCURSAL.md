# Multi-sucursal — contrato de API

Cutter ahora aísla **órdenes, pre-órdenes y borradores** por sucursal. Este documento
resume lo que cambia para el frontend (dashboard React). Detalle de auth en
[`AUTH.md`](AUTH.md).

## Modelo

- **Sucursal (`branch`)** es una entidad real (`/branches`). Reemplaza al JSON de
  membrete que vivía en `settings.company_branches`.
- Cada **usuario** staff (`vendedor`/`operador`) tiene **una** sucursal base
  (`branchId`). El **operador** está atado a ella (solo ve/opera la suya). El
  **vendedor** y el **administrador** son **globales**: ven y operan todas las
  sucursales. El `branchId` del vendedor es su sucursal **base** (default al crear,
  sobrescribible); el del administrador es nulo.
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
| `vendedor` | **Todas** las sucursales; filtro opcional `?branchId=` | Predetermina su sucursal base; puede sobrescribirla con `branchId` |
| `operador` | Solo **su** sucursal | Hereda su sucursal (el `branchId` del body se ignora) |

Un recurso de otra sucursal devuelve **404** (no 403): no se revela que existe. (El
`operador` no crea órdenes/pre-órdenes/borradores; su columna "Crear" es la regla genérica.)

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
- **Pre-órdenes** (`POST /preorders`): acepta `branchId`. El operador lo ignora (hereda
  el suyo); el **vendedor** puede omitirlo (cae en su sucursal base) o enviarlo para
  crear en otra sucursal; el admin debe enviarlo. `GET /preorders` acepta `?branchId=`
  para los roles globales (admin/vendedor).
- **Órdenes** (`GET /orders`): acepta `?branchId=` para los roles globales
  (admin/vendedor). La orden nace con la sucursal de la pre-orden al confirmar; su
  proforma/hoja de producción muestran esa sucursal en el membrete.
- **Borradores** (`POST /optimization-drafts`): acepta `branchId` (mismo criterio que
  pre-órdenes); `GET` acepta `?branchId=` (admin/vendedor).

## Errores relevantes

- `422 VALIDATION_ERROR` (`field: "branchId"`): admin creando sin indicar sucursal, o
  sucursal inactiva.
- `403 FORBIDDEN`: operador sin sucursal asignada (estado inválido a corregir por el admin).
- `404 NOT_FOUND`: acceso a un recurso de otra sucursal (uniforme con "no existe").
