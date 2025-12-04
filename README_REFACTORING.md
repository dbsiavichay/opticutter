# Refactorización a Clean Architecture

## Resumen de Cambios

Se ha reorganizado completamente el proyecto siguiendo los principios de **Clean Architecture**, separando las responsabilidades en capas bien definidas y eliminando el acoplamiento entre componentes.

## Cambios Principales

### 1. Nueva Estructura de Carpetas

```
src/
├── api/v1/                  # Capa de Presentación
│   ├── routes/              # Endpoints HTTP
│   └── schemas/             # Modelos Pydantic para API
├── application/             # Capa de Aplicación
│   └── services/            # Casos de uso
├── domain/                  # Capa de Dominio
│   ├── models/cutting/      # Modelos de dominio
│   └── services/            # Servicios de dominio
├── infrastructure/          # Capa de Infraestructura
│   └── database/
│       ├── models/          # Modelos ORM
│       └── repositories/    # Repositorios
└── core/                    # Utilidades y configuración
    ├── config/              # Configuración
    ├── exceptions/          # Excepciones personalizadas
    └── utils/               # Utilidades
```

### 2. Patrón Repository

Se implementó el patrón Repository para abstraer el acceso a datos:

**Antes**:
```python
# En el servicio
db.query(ClientModel).filter(ClientModel.id == client_id).first()
```

**Ahora**:
```python
# Repository
class ClientRepository(BaseRepository[ClientModel]):
    def get_by_phone(self, phone: str) -> Optional[ClientModel]:
        return self.db.query(ClientModel).filter(ClientModel.phone == phone).first()

# En el servicio
class ClientService:
    def __init__(self, db: Session):
        self.repository = ClientRepository(db)
    
    def get_client_by_phone(self, phone: str):
        return self.repository.get_by_phone(phone)
```

### 3. Separación de Schemas

Los schemas ahora están claramente separados por contexto:

- **API Schemas** (`src/api/v1/schemas/`): Request/Response de la API
- **Domain Models** (`src/domain/models/`): Modelos de negocio puros
- **ORM Models** (`src/infrastructure/database/models/`): Modelos de base de datos

### 4. Servicios con Inyección de Dependencias

**Antes** (métodos estáticos):
```python
class ClientService:
    @staticmethod
    def create_client(db: Session, client_data: ClientCreate):
        ...
```

**Ahora** (instancias con DI):
```python
class ClientService:
    def __init__(self, db: Session):
        self.repository = ClientRepository(db)
    
    def create_client(self, client_data: ClientCreate):
        ...
```

### 5. Configuración Centralizada

La configuración se movió de `config/` a `src/core/config/`:
- `base.py`: Configuración base
- `local.py`: Desarrollo
- `staging.py`: Staging
- `production.py`: Producción

### 6. Actualización de Imports

Todos los imports se actualizaron para reflejar la nueva estructura:

**Antes**:
```python
from src.models.models import ClientModel
from src.models.schemas import ClientCreate
from src.services.client_service import ClientService
```

**Ahora**:
```python
from src.infrastructure.database.models import ClientModel
from src.api.v1.schemas import ClientCreate
from src.application.services import ClientService
```

## Beneficios de los Cambios

### 1. Separación de Responsabilidades
Cada capa tiene una responsabilidad clara y única.

### 2. Testabilidad Mejorada
Cada componente puede ser testeado independientemente:
- Servicios de dominio sin necesidad de base de datos
- Repositories con mocks
- API endpoints con servicios mockeados

### 3. Mantenibilidad
- Código más organizado y fácil de navegar
- Cambios en una capa no afectan otras capas
- Fácil localizar dónde hacer cambios

### 4. Flexibilidad
- Fácil cambiar implementaciones (ej: cambiar de SQLite a PostgreSQL)
- Fácil agregar nuevas funcionalidades
- Fácil reemplazar componentes

### 5. Escalabilidad
- Estructura preparada para crecer
- Patrones establecidos para nuevas features
- Código reutilizable

## Guía de Migración para Desarrolladores

### Agregar un Nuevo Modelo

1. **Modelo de Dominio** (`src/domain/models/`):
```python
# src/domain/models/product.py
class Product:
    def __init__(self, name: str, price: float):
        self.name = name
        self.price = price
```

2. **Modelo ORM** (`src/infrastructure/database/models/`):
```python
# src/infrastructure/database/models/product.py
from sqlalchemy import String, Float
from sqlalchemy.orm import Mapped, mapped_column
from src.infrastructure.database.base import Base

class ProductModel(Base):
    __tablename__ = "products"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    price: Mapped[float] = mapped_column(Float)
```

3. **Repository** (`src/infrastructure/database/repositories/`):
```python
# src/infrastructure/database/repositories/product_repository.py
from src.infrastructure.database.models import ProductModel
from src.infrastructure.database.repositories.base import BaseRepository

class ProductRepository(BaseRepository[ProductModel]):
    def __init__(self, db: Session):
        super().__init__(ProductModel, db)
```

4. **Schema de API** (`src/api/v1/schemas/`):
```python
# src/api/v1/schemas/product.py
from pydantic import BaseModel

class ProductCreate(BaseModel):
    name: str
    price: float

class ProductResponse(BaseModel):
    id: int
    name: str
    price: float
    
    class Config:
        from_attributes = True
```

5. **Servicio de Aplicación** (`src/application/services/`):
```python
# src/application/services/product_service.py
from sqlalchemy.orm import Session
from src.infrastructure.database.repositories import ProductRepository
from src.api.v1.schemas import ProductCreate

class ProductService:
    def __init__(self, db: Session):
        self.repository = ProductRepository(db)
    
    def create_product(self, product_data: ProductCreate):
        product = ProductModel(
            name=product_data.name,
            price=product_data.price
        )
        return self.repository.create(product)
```

6. **Endpoint de API** (`src/api/v1/routes/`):
```python
# src/api/v1/routes/products.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from src.api.v1.schemas import ProductCreate, ProductResponse
from src.application.services import ProductService
from src.infrastructure.database import get_db

router = APIRouter(prefix="/products", tags=["products"])

@router.post("/", response_model=ProductResponse)
async def create_product(
    product_data: ProductCreate,
    db: Session = Depends(get_db)
):
    service = ProductService(db)
    return service.create_product(product_data)
```

### Trabajar con la Nueva Estructura

#### Ejecutar la Aplicación
```bash
source .venv/bin/activate
python main.py
```

#### Crear Migraciones
```bash
alembic revision --autogenerate -m "descripción"
alembic upgrade head
```

#### Tests
Los tests ahora pueden ser organizados por capa:
```
tests/
├── api/           # Tests de endpoints
├── application/   # Tests de servicios
├── domain/        # Tests de lógica de negocio
└── infrastructure # Tests de repositorios
```

## Archivos Antiguos

Los siguientes archivos/carpetas **pueden ser eliminados** una vez verificado que todo funciona:

- `config/` (movido a `src/core/config/`)
- `src/models/` (separado en domain/models y infrastructure/database/models)
- `src/schemas/` (movido a `src/api/v1/schemas/`)
- `src/services/` (movido a `src/application/services/` y `src/domain/services/`)
- `src/db/` (movido a `src/infrastructure/database/`)
- `src/utils/` (movido a `src/core/utils/`)

**Nota**: No eliminar hasta estar seguro de que la aplicación funciona correctamente.

## Próximos Pasos Recomendados

1. **Agregar Tests**
   - Tests unitarios para servicios de dominio
   - Tests de integración para repositories
   - Tests de API con mocks

2. **Implementar Cache**
   - Agregar Redis para caching de optimizaciones
   - Implementar en `src/infrastructure/cache/`

3. **Agregar Logging**
   - Logging estructurado
   - Implementar en `src/core/logging/`

4. **Documentación**
   - Documentar cada servicio
   - Agregar ejemplos de uso
   - Documentar flujos de datos

5. **Manejo de Excepciones**
   - Centralizar manejo de errores
   - Implementar middleware de excepciones

## Recursos Adicionales

- [Clean Architecture](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)
- [Repository Pattern](https://martinfowler.com/eaaCatalog/repository.html)
- [Domain-Driven Design](https://martinfowler.com/tags/domain%20driven%20design.html)

## Contacto y Soporte

Para preguntas sobre la nueva arquitectura, consultar el archivo `ARCHITECTURE.md` o contactar al equipo de desarrollo.
