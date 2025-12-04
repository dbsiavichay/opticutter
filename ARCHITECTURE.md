# Arquitectura del Proyecto Cutter

## Visión General

Este proyecto ha sido reorganizado siguiendo los principios de **Clean Architecture**. La arquitectura se divide en capas bien definidas, cada una con responsabilidades específicas y dependencias claras.

## Estructura de Capas

```
src/
├── api/                    # Capa de Presentación (API)
│   └── v1/
│       ├── routes/         # Controladores/Endpoints
│       └── schemas/        # Modelos de Request/Response (Pydantic)
├── application/            # Capa de Aplicación
│   └── services/           # Casos de Uso / Servicios de Aplicación
├── domain/                 # Capa de Dominio
│   ├── models/            # Modelos de Dominio
│   │   └── cutting/       # Modelos específicos de corte
│   └── services/          # Servicios de Dominio (Algoritmos)
├── infrastructure/         # Capa de Infraestructura
│   └── database/
│       ├── models/        # Modelos ORM (SQLAlchemy)
│       └── repositories/  # Repositorios de Datos
└── core/                  # Capa Central
    ├── config/            # Configuración de la aplicación
    ├── exceptions/        # Excepciones personalizadas
    └── utils/             # Utilidades compartidas
```

## Descripción de Capas

### 1. Capa de Presentación (API)

**Responsabilidad**: Manejar las solicitudes HTTP y las respuestas.

**Componentes**:
- **Routes** (`src/api/v1/routes/`): Controladores que definen los endpoints de la API
  - `boards.py`: CRUD de tableros
  - `clients.py`: CRUD de clientes
  - `optimize.py`: Endpoint de optimización
  - `health.py`: Endpoints de salud
  - `cutter.py`: Información del servicio

- **Schemas** (`src/api/v1/schemas/`): Modelos Pydantic para validación de entrada/salida
  - `board.py`: Schemas de Board (Create, Update, Response)
  - `client.py`: Schemas de Client (Create, Update, Response)
  - `optimization.py`: Schemas de optimización (Request, Response)
  - `cutting.py`: Schemas de parámetros de corte

**Principios**:
- No contiene lógica de negocio
- Solo valida datos y delega a servicios de aplicación
- Maneja respuestas HTTP y errores

### 2. Capa de Aplicación

**Responsabilidad**: Orquestar la lógica de negocio y coordinar operaciones.

**Componentes**:
- **Services** (`src/application/services/`): Casos de uso de la aplicación
  - `board_service.py`: Operaciones CRUD de tableros
  - `client_service.py`: Operaciones CRUD de clientes
  - `optimization_service.py`: Orquestación de optimización

**Principios**:
- Coordina entre repositorios y servicios de dominio
- Maneja transacciones
- Transforma entre modelos de dominio y modelos de API

### 3. Capa de Dominio

**Responsabilidad**: Contener la lógica de negocio pura y los modelos de dominio.

**Componentes**:
- **Models** (`src/domain/models/cutting/`):
  - `__init__.py`: Modelos básicos (Rectangle, Piece, PlacedPiece, Material)
  - `layout.py`: CuttingLayout
  - `parameters.py`: CuttingParameters
  - `enums.py`: SplitRule

- **Services** (`src/domain/services/`):
  - `guillotine_optimizer.py`: Algoritmo de optimización guillotina

**Principios**:
- No depende de otras capas
- Contiene lógica de negocio pura
- Modelos de dominio ricos en comportamiento

### 4. Capa de Infraestructura

**Responsabilidad**: Implementar detalles técnicos y acceso a datos.

**Componentes**:
- **Database** (`src/infrastructure/database/`):
  - `base.py`: Clase base para ORM
  - `session.py`: Configuración de sesión de base de datos
  - **Models** (`models/`):
    - `board.py`: Modelo ORM de Board
    - `client.py`: Modelo ORM de Client
    - `optimization.py`: Modelo ORM de Optimization
  - **Repositories** (`repositories/`):
    - `base.py`: Repository genérico
    - `board_repository.py`: Repository de Board
    - `client_repository.py`: Repository de Client
    - `optimization_repository.py`: Repository de Optimization

**Principios**:
- Implementa interfaces definidas por capas superiores
- Maneja persistencia de datos
- Patrón Repository para abstraer acceso a datos

### 5. Capa Central (Core)

**Responsabilidad**: Proporcionar utilidades y configuración compartida.

**Componentes**:
- **Config** (`src/core/config/`):
  - `base.py`: Configuración base
  - `local.py`: Configuración de desarrollo
  - `staging.py`: Configuración de staging
  - `production.py`: Configuración de producción

- **Exceptions** (`src/core/exceptions/`):
  - `base.py`: Excepciones personalizadas

- **Utils** (`src/core/utils/`):
  - `hash.py`: Utilidades de hash

## Principios de Clean Architecture Aplicados

### 1. Separación de Responsabilidades
Cada capa tiene una responsabilidad específica y bien definida.

### 2. Dependencia Invertida
Las capas internas no dependen de las externas. El flujo de dependencias va:
```
API → Application → Domain
     Infrastructure → Domain
```

### 3. Independencia de Frameworks
La lógica de negocio (Domain) no depende de FastAPI, SQLAlchemy, etc.

### 4. Testabilidad
Cada capa puede ser testeada independientemente usando mocks.

### 5. Independencia de Base de Datos
La lógica de negocio no depende del motor de base de datos específico.

## Flujo de Datos

### Ejemplo: Optimización de Cortes

1. **API Layer**: Recibe la solicitud HTTP
   - `optimize.py` recibe el request
   - Valida con `OptimizeRequest` schema

2. **Application Layer**: Orquesta el proceso
   - `OptimizationService` coordina la operación
   - Obtiene tableros usando `BoardService`
   - Agrupa requerimientos por tablero

3. **Domain Layer**: Ejecuta la lógica de negocio
   - `GuillotineOptimizer` calcula el layout óptimo
   - Usa modelos de dominio (`Material`, `Piece`, `CuttingLayout`)

4. **Infrastructure Layer**: Persiste los datos
   - `OptimizationRepository` guarda el resultado
   - `BoardRepository` obtiene información de tableros

5. **API Layer**: Retorna la respuesta
   - Convierte resultado a `OptimizeResponse`
   - Retorna JSON al cliente

## Ventajas de Esta Arquitectura

1. **Mantenibilidad**: Código organizado y fácil de entender
2. **Escalabilidad**: Fácil agregar nuevas funcionalidades
3. **Testabilidad**: Cada capa puede ser testeada independientemente
4. **Flexibilidad**: Fácil cambiar implementaciones (ej: cambiar de DB)
5. **Claridad**: Flujo de datos y responsabilidades claras

## Patrones de Diseño Utilizados

- **Repository Pattern**: Para abstraer el acceso a datos
- **Service Pattern**: Para encapsular lógica de negocio
- **DTO Pattern**: Schemas de API para transferencia de datos
- **Dependency Injection**: A través de FastAPI Depends

## Convenciones de Código

- Los modelos ORM se nombran con sufijo `Model` (ej: `BoardModel`)
- Los schemas de API se nombran con sufijos descriptivos (ej: `BoardCreate`, `BoardResponse`)
- Los servicios se nombran con sufijo `Service` (ej: `OptimizationService`)
- Los repositorios se nombran con sufijo `Repository` (ej: `BoardRepository`)

## Próximos Pasos Recomendados

1. Agregar tests unitarios para cada capa
2. Implementar cache con Redis
3. Agregar logging estructurado
4. Implementar manejo de excepciones centralizado
5. Agregar métricas y monitoreo
