# Validación de la infraestructura

## Automática

GitHub Actions ejecuta `bash infra/test-infra.sh` en Linux para cada push, pull
request y ejecución manual. Se requieren Docker Engine, Compose v2, Bash, Python 3
y OpenSSL. Puede ejecutarse también localmente en Linux desde la raíz.

La prueba genera sus propias credenciales y dos proyectos `brota-ci-*` únicos:

1. Renderiza Compose de desarrollo y servidor y verifica persistencia, secreto,
   healthcheck, puerto localhost en desarrollo y ausencia de puerto en servidor.
2. Arranca una base vacía y comprueba SQL por TCP con contraseña.
3. Crea un esquema marcador exclusivo de prueba, recrea el contenedor y verifica
   su persistencia.
4. Genera un dump binario, lo restaura en otra instancia con volumen separado y
   comprueba el marcador.
5. Elimina exclusivamente los proyectos y volúmenes temporales creados por el script.

No añade tablas de negocio a la instalación. No publica imágenes ni despliega.
El entorno temporal requiere salida al registro Docker para descargar PostgreSQL.

Para validar solo la configuración sin arrancar contenedores, después de preparar
el entorno y secreto locales, usar:

```text
python infra/check-config.py infra/env/dev.env
```

## Aceptación manual

- Desde un clon limpio, seguir el README hasta que `ps` indique `healthy` y SQL responda.
- Comprobar que la base inicial no tiene tablas de aplicación.
- Detener con `down` y arrancar otra vez sin regenerar credenciales ni eliminar volúmenes.
- Repetir con el entorno de servidor y comprobar que no hay puerto publicado.
- Realizar respaldo y restauración de comprobación siguiendo la guía de operación.
- Al incorporar API/paneles, añadir sus pruebas de arranque, disponibilidad y conectividad.

## Estado al preparar esta base

El equipo de autoría usa Windows/PowerShell y no tiene Docker disponible en PATH.
Por tanto, las instrucciones de arranque en Windows y Linux, la descarga de la
imagen y el ciclo de base de datos no están comprobados aquí. La validación
integral queda preparada en Actions; su resultado debe revisarse tras subir el
cambio. No interpretar la presencia del workflow como una ejecución exitosa.

La comprobación local cubre estructura YAML, sintaxis Python y Bash (`bash -n`),
contratos estáticos de Compose, enlaces locales, finales LF y exclusión de secretos.
La validación de Compose
resuelto requiere el CLI Docker, y las pruebas de ciclo de vida requieren su daemon.
