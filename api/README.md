# Incorporar la API

El framework se elegirá con las reglas del reto. Aquí se añadirá su proyecto y
Dockerfile cuando se confirme. Contrato y ejemplo de integración en
[docs/integracion.md](../docs/integracion.md).

La primera integración debe arrancar el servidor, recibir configuración externa y
exponer `/health/live` y `/health/ready`. La disponibilidad comprobará PostgreSQL.
El esquema, las migraciones, los roles de aplicación y el dominio se definirán
con el contexto del reto.
