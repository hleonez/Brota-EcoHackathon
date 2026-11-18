# Credenciales locales

Los archivos de esta carpeta están excluidos de Git. Sigue el README principal
para generar una contraseña distinta por entorno. No subas secretos al repositorio.

Compose monta el archivo en `/run/secrets/db_password`. Esto no cifra el archivo
del host: restringe su acceso y conserva una copia en el gestor de secretos del equipo.
En Windows se usan contenedores Linux mediante Docker Desktop/WSL2.
