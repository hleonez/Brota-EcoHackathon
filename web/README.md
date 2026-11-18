# Incorporar los paneles

El framework se elegirá durante la hackathon. Cada aplicación podrá ocupar una
subcarpeta y tendrá una imagen independiente. Se admiten archivos estáticos
servidos por un contenedor o aplicaciones con servidor.

Consulta [el contrato de integración](../docs/integracion.md). Configura la URL
pública de la API según el despliegue. Las variables que llegan al navegador son
públicas: nunca deben contener contraseñas de base de datos o claves privadas.

## Espacios de trabajo

| Panel provisional | Carpeta | Puerto local propuesto |
| --- | --- | --- |
| Coordinación | [coordinacion/](coordinacion/README.md) | 3000 |
| Fundación | [fundacion/](fundacion/README.md) | 3001 |

Los nombres se basan en el plan maestro y se ajustarán con el contexto del reto.
Por ahora cada espacio contiene instrucciones. No hay proyectos de framework,
dependencias ni comandos de arranque ejecutables.

## Convenciones comunes

- Generar cada aplicación dentro de su carpeta y documentar su instalación y
  comando de desarrollo en su README. Usar una terminal por aplicación.
- Configurar puertos distintos. La API compartida usará inicialmente el puerto 8000.
- La URL pública de API para desarrollo será `http://localhost:8000`. Elegir el
  nombre de variable que admita el framework y documentar si se lee al compilar
  o al ejecutar. No asumir que cambiar una variable del contenedor modifica un
  frontend ya compilado.
- Para mismo dominio en el servidor, usar `/api`; para servicios separados, la
  URL HTTPS pública de la API. El navegador nunca debe usar el hostname interno `db`.
- Si se añaden archivos `.env`, incluir sus ejemplos sin secretos y comprobar
  que los archivos privados quedan excluidos de Git.
- Añadir Dockerfiles y servicios Compose cuando existan aplicaciones funcionales.

Si ambos paneles comparten framework e interfaz, se podrá optar por una sola
aplicación con rutas y permisos diferentes. Antes de generarlos, registrar esa
decisión aquí y ajustar las carpetas para evitar mantener dos aplicaciones iguales.
