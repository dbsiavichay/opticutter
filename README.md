# Cutter API

API para el sistema Cutter de Maderable desarrollada con FastAPI.

## Características

- ✅ FastAPI con documentación automática
- ✅ Configuración por entornos (local, staging, production)
- ✅ Middlewares para manejo de errores y logging
- ✅ Estructura modular y escalable
- ✅ Docker y Docker Compose
- ✅ Linting y formateo de código
- ✅ Tests con pytest
- ✅ Health checks

## Estructura del Proyecto

```
├── config/                 # Configuraciones por entorno
│   ├── base.py            # Configuración base
│   ├── local.py           # Configuración local
│   ├── staging.py         # Configuración staging
│   └── production.py      # Configuración producción
├── src/
│   ├── api/               # Rutas y endpoints
│   │   ├── endpoints/     # Endpoints específicos
│   │   └── routes.py      # Router principal
│   ├── core/              # Funcionalidades core
│   │   └── middlewares.py # Middlewares personalizados
│   ├── models/            # Modelos de base de datos
│   └── schemas/           # Esquemas Pydantic
├── tests/                 # Tests
├── main.py               # Punto de entrada
├── requirements.txt      # Dependencias
├── Dockerfile           # Imagen Docker
├── docker-compose.yml   # Servicios Docker
└── Makefile            # Comandos útiles
```

## Instalación y Configuración

### 1. Clonar el repositorio

```bash
git clone <repository-url>
cd Cutter
```

### 2. Configurar variables de entorno

```bash
make setup
# O manualmente:
cp .env.example .env
```

Edita el archivo `.env` según tus necesidades.

### 3. Usando Docker (Recomendado)

```bash
# Construir la imagen
make build

# Iniciar en modo desarrollo
make dev

# O iniciar en modo daemon
make start
```

### 4. Instalación local

```bash
# Instalar dependencias
make install

# Ejecutar localmente
make run-local
```

## Uso

### Endpoints disponibles

- **GET /** - Redirige a la documentación
- **GET /docs** - Documentación Swagger
- **GET /redoc** - Documentación ReDoc
- **GET /health** - Health check básico
- **GET /api/v1/health/** - Health check detallado
- **GET /api/v1/health/ready** - Readiness check
- **GET /api/v1/cutter/** - Información del sistema Cutter

### Comandos útiles

```bash
# Ver ayuda
make help

# Desarrollo
make dev                    # Iniciar en modo desarrollo
make logs                   # Ver logs
make shell                  # Abrir shell en contenedor

# Testing
make tests                  # Ejecutar tests en Docker
make tests-local           # Ejecutar tests localmente

# Linting
make lint-check            # Verificar formato
make lint-fix              # Corregir formato

# Limpieza
make clean                 # Limpiar Docker
make down                  # Detener contenedores
```

## Configuración por Entornos

El proyecto soporta múltiples entornos:

- **local**: Desarrollo local con debug habilitado
- **staging**: Entorno de pruebas
- **production**: Entorno de producción

Cambia el entorno modificando la variable `ENVIRONMENT` en tu archivo `.env`.

## Variables de Entorno

| Variable | Descripción | Default |
|----------|-------------|---------|
| `ENVIRONMENT` | Entorno de ejecución | `local` |
| `LOG_LEVEL` | Nivel de logging | `DEBUG` |
| `HOST` | Host del servidor | `0.0.0.0` |
| `PORT` | Puerto del servidor | `3000` |
| `DEBUG` | Modo debug | `true` |
| `SECRET_KEY` | Clave secreta para JWT | `your-secret-key...` |
| `DATABASE_URL` | URL de la base de datos | `sqlite:///./cutter_local.db` |
| `REDIS_URL` | URL de Redis | `redis://localhost:6379/0` |

Ver `.env.example` para la lista completa.

## Desarrollo

### Agregar nuevos endpoints

1. Crear el endpoint en `src/api/endpoints/`
2. Agregar el router en `src/api/routes.py`
3. Crear esquemas en `src/schemas/` si es necesario

### Agregar middlewares

1. Crear el middleware en `src/core/middlewares.py`
2. Agregarlo en `main.py`

### Tests

```bash
# Ejecutar todos los tests
make tests

# Ejecutar tests específicos
pytest tests/test_specific.py

# Con coverage
pytest --cov=src tests/
```

## Despliegue

### Docker

```bash
# Construir para producción
docker build -t cutter-api .

# Ejecutar
docker run -p 3000:3000 --env-file .env cutter-api
```

### Docker Compose

```bash
# Producción
ENVIRONMENT=production docker-compose up -d
```

## Contribución

1. Fork el proyecto
2. Crea una rama para tu feature (`git checkout -b feature/AmazingFeature`)
3. Commit tus cambios (`git commit -m 'Add some AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abre un Pull Request

## Licencia

Este proyecto está bajo la licencia MIT. Ver `LICENSE` para más detalles.