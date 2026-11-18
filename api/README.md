# Incorporar la API

Propuesta funcional editable: [contrato modular de API](../docs/contrato-api.md).
Es un borrador para acordar con el equipo antes de implementar el dominio.

El framework se elegirá con las reglas del reto. Aquí se añadirá su proyecto y
Dockerfile cuando se confirme. Contrato y ejemplo de integración en
[docs/integracion.md](../docs/integracion.md).

La primera integración debe arrancar el servidor, recibir configuración externa y
exponer `/health/live` y `/health/ready`. La disponibilidad comprobará PostgreSQL.
El esquema, las migraciones, los roles de aplicación y el dominio se definirán
con el contexto del reto.

## Preparar el backend durante la hackathon

1. Generar el proyecto del framework elegido dentro de `api/`. Como esta carpeta
   ya contiene documentación, generar en una carpeta temporal si la herramienta
   exige un destino vacío y trasladar después sus archivos aquí, conservando esta guía.
2. Copiar `.env.example` a `.env` y adaptar la lectura de variables al framework.
   El archivo `.env` no se carga automáticamente: deberá hacerlo la aplicación o
   su comando de arranque. Está excluido de Git.
3. Levantar PostgreSQL desde la raíz siguiendo el [README principal](../README.md).
   Para ejecutar la API en el equipo, usar `DB_HOST=127.0.0.1` y el puerto publicado.
4. Crear el rol de conexión de la aplicación cuando se conozcan sus permisos;
   completar `DB_USER` y `DB_PASSWORD` localmente. No incluir credenciales en Git.
5. Configurar el puerto 8000, los orígenes de los paneles y las comprobaciones
   de salud descritas en el contrato. La configuración de CORS deberá adaptarse
   explícitamente al framework.
6. Registrar aquí los comandos reales de instalación, desarrollo y comprobación
   cuando exista la aplicación. Ejecutar el backend en una terminal independiente.

## Variables locales

El ejemplo de esta carpeta está pensado para ejecutar la API fuera de Docker.
`infra/env/app.env.example` describe la variante dentro de la red Compose.
`PORT` y `CORS_ALLOWED_ORIGINS` son convenciones propuestas que deberá leer el
backend; no configuran un framework por sí solas. La lista de orígenes se separa
por comas y contiene URLs exactas.

En producción se configurará `/api` como prefijo público. En desarrollo directo,
los paneles usarán `http://localhost:8000` como base y la API servirá sin ese prefijo.
El adaptador del framework documentará cómo configura cada caso.

## Despliegue posterior

Añadir Dockerfile y servicio Compose al existir una API ejecutable. La conexión
dentro de Compose usará `db:5432`, independientemente del puerto publicado en el
equipo. Una sola API atenderá inicialmente los dos paneles; sus permisos se
definirán con el contexto del reto.
