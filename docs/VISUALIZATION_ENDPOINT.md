# Endpoint de Visualización de Optimización

## Nuevo Endpoint: GET /api/v1/optimize/visualize/{request_hash}

### Descripción
Este endpoint genera una imagen visual de los resultados de optimización de cortes basada en el hash de una optimización previamente calculada y almacenada en caché.

### Parámetros
- `request_hash` (string, required): El hash identificador de la optimización cacheada

### Respuesta
```json
{
  "image_base64": "iVBORw0KGgoAAAANSUhEUgAA...", // Imagen PNG en base64
  "content_type": "image/png",
  "request_hash": "abc123...",
}
```

### Códigos de Error
- `404`: No se encontró optimización con el hash proporcionado
- `400`: No se encontraron tableros para visualizar
- `500`: Error interno al generar la visualización

### Ejemplo de Uso

1. **Primero, realizar una optimización:**
```bash
curl -X POST "http://localhost:3000/api/v1/optimize" \
  -H "Content-Type: application/json" \
  -d '{
    "cuts": [
      {
        "width": 600,
        "height": 400,
        "quantity": 2,
        "material": "MEL18",
        "label": "Estante Superior"
      }
    ],
    "materials": [
      {
        "code": "MEL18",
        "width": 1220,
        "height": 2440,
        "price": 45.50
      }
    ],
    "cutting_parameters": {
      "kerf": 5,
      "top_trim": 0,
      "bottom_trim": 0,
      "left_trim": 0,
      "right_trim": 0
    }
  }'
```

2. **Tomar el hash de la respuesta y solicitar la visualización:**
```bash
curl -X GET "http://localhost:3000/api/v1/optimize/visualize/{hash_obtenido}"
```

3. **Usar la imagen base64 en el frontend:**
```html
<img src="data:image/png;base64,{image_base64}" alt="Optimización de Cortes" />
```

### Características de la Visualización

#### Elementos Visuales
- **Tableros**: Rectangulos con bordes negros
- **Cortes**: Rectangulos azules con etiquetas y dimensiones
- **Residuos**: Rectangulos rojos para desperdicios
- **Información**: Título general, información por tablero y porcentaje de aprovechamiento

#### Colores
- **Fondo**: Blanco (#FFFFFF)
- **Tableros**: Borde negro (#000000)
- **Cortes**: Azul claro con borde azul (#E3F2FD / #1976D2)
- **Residuos**: Rosa claro con borde rojo (#FFEBEE / #D32F2F)
- **Texto**: Gris oscuro (#212121)

#### Layout Automático
- Los tableros se organizan automáticamente en filas
- Escala automática para mantener legibilidad
- Dimensiones mínimas para asegurar visibilidad
- Espaciado apropiado entre elementos

### Implementación Técnica

#### Archivos Modificados/Creados:
1. `src/services/visualization.py` - Servicio principal de visualización
2. `src/models/schemas.py` - Nuevo schema `OptimizationImageResponse`
3. `src/api/optimize.py` - Nuevo endpoint
4. `requirements.txt` - Añadida dependencia `Pillow==10.4.0`

#### Dependencias Añadidas:
- **Pillow (PIL)**: Para generación de imágenes
- Manejo de fuentes automático con fallbacks

#### Consideraciones de Rendimiento:
- Caché de imágenes basado en hash (las imágenes se regeneran cada vez)
- Optimización de tamaño de imagen para web
- Manejo eficiente de memoria con PIL

### Posibles Mejoras Futuras

1. **Caché de Imágenes**: Almacenar imágenes generadas en Redis para evitar regeneración
2. **Personalización**: Permitir personalizar colores y estilos
3. **Formatos Adicionales**: Soporte para SVG, PDF
4. **Detalles Adicionales**: Mostrar información de costos, kerf, etc.
5. **Dimensiones Exactas**: Almacenar dimensiones originales de materiales en cache

### Notas de Desarrollo

- Las dimensiones de los materiales se estiman basándose en los cortes colocados
- Se utilizan tamaños estándar de tableros de melamina para aproximaciones
- La implementación es tolerante a fallos con mensajes de error descriptivos
- Compatible con contenedores Docker (fuentes del sistema disponibles)