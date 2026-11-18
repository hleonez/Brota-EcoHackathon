# Panel de coordinación

Espacio provisional para la interfaz de coordinación. Las pantallas y permisos se
definirán al conocer el reto; el nombre no fija funcionalidades del plan maestro.

## Incorporar la aplicación

1. Generar el proyecto del framework elegido en esta carpeta. Si el generador
   exige una carpeta vacía, usar un destino temporal y trasladar sus archivos,
   conservando esta guía.
2. Configurar el servidor de desarrollo en el puerto 3000.
3. Configurar la URL pública de API en `http://localhost:8000` mediante el mecanismo
   del framework. Registrar aquí el nombre de variable y cuándo se consume.
4. Documentar los comandos reales de instalación y arranque; ejecutar el panel
   en su propia terminal y comprobar la comunicación con la API.

Los comandos y la variable de URL quedan pendientes de elegir framework.
La API deberá permitir el origen `http://localhost:3000` durante desarrollo.
No añadir credenciales de PostgreSQL a esta aplicación.

Para despliegue se añadirá su Dockerfile, o se integrará como parte de una web
compartida si así lo decide el equipo. Consulta las [convenciones comunes](../README.md)
y el [contrato de integración](../../docs/integracion.md).
