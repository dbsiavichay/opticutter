# Configuración de Base de Datos

Este proyecto ha sido configurado para usar SQLAlchemy con Alembic para las migraciones de base de datos.

## Configuración inicial

1. **Instalar dependencias**: Las dependencias ya están agregadas en `requirements.txt`
   ```bash
   pip install -r requirements.txt
   ```

2. **Configurar variables de entorno**: Copia el archivo `.env.example` a `.env` 
   ```bash
   cp .env.example .env
   ```

3. **Base de datos por defecto**: El proyecto está configurado para usar SQLite3 por defecto:
   ```
   DATABASE_URL=sqlite:///./cutter_local.db
   ```

## Estructura de archivos

- `config/database.py`: Configuración de SQLAlchemy
- `src/models/`: Directorio donde irán los modelos de base de datos
- `alembic/`: Configuración y migraciones de Alembic
- `alembic.ini`: Archivo de configuración de Alembic

## Uso básico de Alembic

### Crear una migración inicial
```bash
alembic revision --autogenerate -m "Initial migration"
```

### Aplicar migraciones
```bash
alembic upgrade head
```

### Crear nueva migración después de cambios en modelos
```bash
alembic revision --autogenerate -m "Add new table"
```

### Ver historial de migraciones
```bash
alembic history
```

### Revertir migración
```bash
alembic downgrade -1
```

## Creación de modelos

1. Crea tus modelos en `src/models/` (ej: `src/models/user.py`)
2. Importa el modelo en `src/models/models.py`
3. Descomenta la línea de importación en `alembic/env.py`:
   ```python
   from src.models import models
   ```
4. Crea y aplica la migración:
   ```bash
   alembic revision --autogenerate -m "Add User model"
   alembic upgrade head
   ```

## Uso en FastAPI

Para usar la base de datos en tus endpoints:

```python
from fastapi import Depends
from sqlalchemy.orm import Session
from config.database import get_db

@app.get("/example")
def get_data(db: Session = Depends(get_db)):
    # Tu código aquí
    return {"data": "example"}
```

## Cambio de base de datos

Para cambiar a PostgreSQL o MySQL, solo cambia la `DATABASE_URL` en tu `.env`:

```bash
# PostgreSQL
DATABASE_URL=postgresql://user:password@localhost:5432/cutter_db

# MySQL
DATABASE_URL=mysql://user:password@localhost:3306/cutter_db
```

Y asegúrate de instalar el driver correspondiente:
```bash
pip install psycopg2-binary  # Para PostgreSQL
# o
pip install pymysql         # Para MySQL
```