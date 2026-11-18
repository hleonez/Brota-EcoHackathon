# Tutorial de Neon e integración con Brota

Guía para PowerShell, preparada el 18 de noviembre de 2026. Comandos contrastados con `neon --help` y la CLI **8.11.0** instalada en este equipo. Los pasos se ejecutan cuando se decida usar Neon; esta guía no crea recursos remotos ni cambia la conexión actual.

## 1. Qué aporta Neon y dónde encaja

Neon proporciona PostgreSQL gestionado. En Brota ocuparía el lugar del PostgreSQL que hoy levanta Docker. La conexión se realiza desde la API; los paneles siguen hablando con esa API.

```text
WhatsApp / panel de coordinación / panel de Fundación
                         ↓
                    API de Brota
                         ↓ conexión PostgreSQL con TLS
                        Neon
```

No necesitas un servidor de PostgreSQL local para usar Neon. Tampoco hace falta que el backend esté alojado en la nube: durante el desarrollo puede ejecutarse en tu computador y conectarse a Neon por internet. Neon admite clientes PostgreSQL convencionales. [Conexión desde aplicaciones](https://neon.com/docs/connect/connect-from-any-app).

La CLI administra recursos; el controlador PostgreSQL de la futura API ejecutará las consultas. Tener la CLI instalada no conecta automáticamente la aplicación ni convierte el [diseño de datos](diseno-base-de-datos.md) en tablas.

## 2. Conceptos que vas a encontrar

| Concepto | Significado para este proyecto |
| --- | --- |
| Organización | Espacio de Neon donde se agrupan proyectos y miembros del equipo |
| Proyecto | Contenedor de la base de Brota, sus ramas y recursos |
| Rama o branch | Entorno de datos aislado; proponemos una rama `dev` para integración |
| Database | Base PostgreSQL dentro de una rama; puede llamarse `brota` o conservar `neondb` |
| Compute / endpoint | Recurso que recibe las conexiones y ejecuta PostgreSQL |
| Rol PostgreSQL | Usuario técnico de conexión, por ejemplo el propietario o un futuro `brota_app` |
| Connection string | URL con host, base, usuario, contraseña y parámetros de conexión |

**Los roles PostgreSQL no son los roles de negocio de Brota.** Carmen, Rosa y Viviana no necesitan usuarios individuales de Neon. La API usa una identidad técnica para conectarse; después valida si la persona tiene permiso de residente, coordinación o Fundación mediante el modelo de la aplicación. Este tutorial no configura Neon Auth ni decide cómo iniciar sesión en los paneles.

## 3. Entrar con tu cuenta

Abre PowerShell en el repositorio:

```powershell
cd "C:\Users\handr\OneDrive\Documentos\Brota-EcoHackathon"
neon --version
neon login
```

Completa el inicio de sesión en el navegador que abra la CLI. Comprueba luego:

```powershell
neon me
neon orgs list
```

La autenticación de la CLI y la contraseña de PostgreSQL son distintas: iniciar sesión permite administrar Neon, pero la API necesitará su propia conexión de base de datos. No necesita tu sesión personal de CLI para funcionar en el servidor.

## 4. Elegir o crear el proyecto

### Si ya tienes un proyecto

Lista los proyectos:

```powershell
neon projects list
```

Si tu cuenta tiene varias organizaciones o la CLI pide indicar una, usa su ID real:

```powershell
$neonOrgId = 'REEMPLAZAR_POR_ID_ORGANIZACION'
neon projects list --org-id $neonOrgId
```

### Si todavía no tienes proyecto

Puedes crearlo desde [Neon Console](https://console.neon.tech), donde puedes revisar las condiciones y recursos de tu cuenta, o mediante CLI:

```powershell
neon projects create --name brota-hackathon --database brota --pg-version 18 --no-secrets
```

Si hay varias organizaciones, añade `--org-id $neonOrgId`. La región puede elegirse desde la consola o con `--region-id`; para ver las opciones reconocidas por tu versión ejecuta `neon projects create --help`. Elige una región cercana al futuro backend y revisa los límites del plan antes de aprovisionar recursos.

Se propone PostgreSQL 18 para mantener la misma versión mayor que la infraestructura del repositorio. Si una región o tu cuenta no la ofrece, confirma la versión disponible y ajusta la compatibilidad antes de migrar. Neon administra las actualizaciones menores; no se fija su imagen de Docker.

Guarda el ID real del proyecto en una variable de esta terminal:

```powershell
$neonProjectId = 'REEMPLAZAR_POR_ID_PROYECTO'
```

No es la contraseña. Puedes obtenerlo del listado de proyectos. Las variables de PowerShell se pierden al cerrar la terminal: vuelve a declararlas en una sesión nueva.

## 5. Crear una rama para integrar

Inspecciona primero qué ramas existen:

```powershell
neon branches list --project-id $neonProjectId
```

Una rama nueva copia inicialmente el estado de su padre y después puede modificarse sin cambiarlo. También puede incluir los datos que ya existan: no asumas que una rama es una base vacía. La rama inicial puede llamarse `production` si se creó desde la consola o `main` si se creó con la CLI. [Gestión de ramas](https://neon.com/docs/manage/branches).

Si todavía no existe `dev`, créala desde la rama que acabas de identificar:

```powershell
$neonParentBranch = 'REEMPLAZAR_POR_RAMA_PADRE'
neon branches create --project-id $neonProjectId --parent $neonParentBranch --name dev --no-secrets
```

Después indica explícitamente la rama, base y rol que utilizarás:

```powershell
$neonBranch = 'dev'
neon databases list --project-id $neonProjectId --branch $neonBranch
neon roles list --project-id $neonProjectId --branch $neonBranch
```

Con esos resultados, declara los nombres reales. El siguiente ejemplo corresponde a un proyecto creado con base `brota`; cámbialos si tus listados muestran otros nombres:

```powershell
$neonDatabase = 'brota'
$neonOwnerRole = 'brota_owner'
```

Las ramas de Neon y las ramas de Git son independientes. Hacer `git switch` no cambia la base a la que apunta tu API.

## 6. Probar una consulta antes de tocar la API

Ejecuta una consulta de lectura usando la CLI instalada:

```powershell
neon psql $neonBranch --project-id $neonProjectId --database-name $neonDatabase --role-name $neonOwnerRole --ssl verify-full -- -c "SELECT current_database(), current_user, version();"
```

El resultado debe mostrar tu base, el rol elegido y la versión PostgreSQL. Esto comprueba conexión y credenciales, aunque todavía no existan tablas de negocio.

Para comprobar si ya hay tablas:

```powershell
neon psql $neonBranch --project-id $neonProjectId --database-name $neonDatabase --role-name $neonOwnerRole --ssl verify-full -- -c "SELECT table_schema, table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE' ORDER BY table_name;"
```

Una respuesta sin filas es normal si todavía no se aplicaron migraciones. Si tu versión de CLI no dispone de `neon psql`, utiliza el SQL Editor de Neon Console seleccionando exactamente la misma rama y base.

El CLI y el futuro controlador pueden usar almacenes de certificados diferentes. Si falla la validación de certificados, revisa el almacén de confianza del cliente. La política externa del repositorio usa `verify-full`; no reutilices `DB_SSLMODE=disable` para Neon. [Conexión segura](https://neon.com/docs/connect/connect-securely).

## 7. Obtener la conexión directa y la conexión con pool

Para consultar la URL directa:

```powershell
neon connection-string $neonBranch --project-id $neonProjectId --database-name $neonDatabase --role-name $neonOwnerRole --ssl verify-full
```

Para obtener la URL con pool:

```powershell
neon connection-string $neonBranch --project-id $neonProjectId --database-name $neonDatabase --role-name $neonOwnerRole --ssl verify-full --pooled
```

**Estos comandos muestran una contraseña en su salida.** Ejecútalos en tu terminal y conserva la URL como secreto. También puedes obtener los parámetros en Neon Console → **Connect**, seleccionando rama, base y rol. No publiques capturas de esa ventana.

| Conexión | Uso propuesto en Brota |
| --- | --- |
| Directa | Migraciones y operaciones que requieran conservar estado de sesión |
| Con pool, host con `-pooler` | Tráfico de la API si el ORM y el modo de ejecución son compatibles |

El pool de Neon funciona en modo de transacción, con limitaciones para características que dependen de la sesión. Por eso proponemos comenzar con conexión directa para migraciones y evaluar el pool para la API. No todos los frameworks necesitan la misma configuración. [Connection pooling](https://neon.com/docs/connect/connection-pooling).

## 8. Configurar este repositorio

Hoy `api/.env.example` contiene variables separadas y la carpeta `api/` todavía no incluye un backend ejecutable. Hay dos caminos posibles cuando se elija el framework.

### Camino A: conservar las variables existentes

Desde la raíz, crea `api/.env` solamente si no existe:

```powershell
if (-not (Test-Path -LiteralPath 'api/.env')) {
    Copy-Item -LiteralPath 'api/.env.example' -Destination 'api/.env'
}
```

Edita ese archivo con los parámetros reales de **Connect**. Ejemplo ficticio:

```dotenv
PORT=8000
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://localhost:3001
DB_HOST=ep-ejemplo-pooler.us-east-2.aws.neon.tech
DB_PORT=5432
DB_NAME=brota
DB_USER=brota_app
DB_PASSWORD="REEMPLAZAR_POR_SECRETO_REAL"
DB_SSLMODE=verify-full
```

`brota_app` es el nombre propuesto del rol limitado que se creará al integrar; no aparece automáticamente por escribirlo en el archivo. Para la prueba inicial del paso 6 se utiliza el propietario real del proyecto.

El backend deberá leer esas variables y pasarlas al controlador. `DB_SSLMODE` es una convención de este repositorio: no configura TLS por sí sola. Usa el campo de contraseña de la consola si trabajas con variables separadas; una contraseña escapada dentro de una URL no debe copiarse como si fuera su valor original.

### Camino B: usar una URL si el framework la necesita

Si el ORM exige una URL, se acordará adaptar el contrato de configuración. Los nombres siguientes son una propuesta, no variables que el proyecto ya consuma:

```dotenv
DATABASE_URL="postgresql://brota_app:CLAVE_CODIFICADA@ep-ejemplo-pooler.us-east-2.aws.neon.tech/brota?sslmode=verify-full"
MIGRATION_DATABASE_URL="postgresql://brota_owner:CLAVE_CODIFICADA@ep-ejemplo.us-east-2.aws.neon.tech/brota?sslmode=verify-full"
```

Copia las URL completas generadas para cada rol; no construyas contraseñas a mano dentro de ellas. Conserva los parámetros de seguridad adicionales compatibles con el controlador, como `channel_binding` si aparecen. El nombre y formato de la URL de migraciones se adaptarán a la herramienta elegida.

Usa un solo camino como configuración canónica. Si se admiten ambos, documenta cuál prevalece para evitar que una URL antigua conecte a otra rama.

Comprueba que el archivo privado queda ignorado:

```powershell
git check-ignore api/.env
```

Debe devolver `api/.env`. Los secretos se guardan en ese archivo local o en el gestor de variables del despliegue. Los ejemplos versionados conservan valores ficticios.

## 9. Qué hará falta programar el día de la integración

Una vez elegido el framework, el trabajo concreto será:

1. Instalar su controlador PostgreSQL y el mecanismo de migraciones.
2. Hacer que cargue `api/.env` en desarrollo o reciba variables del entorno en despliegue.
3. Crear una configuración de conexión reutilizable con TLS, límites de conexiones y tiempo de espera. No abrir una conexión nueva sin control en cada petición.
4. Conectar `/health/ready` a una consulta pequeña como `SELECT 1`. Responder `200` si funciona y `503` si falla, sin exponer credenciales. `/health/live` comprueba el proceso, independientemente de Neon.
5. Traducir el diseño aprobado a migraciones y aplicarlas con conexión directa y un rol autorizado para DDL.
6. Conectar la ejecución normal con `brota_app` y los permisos mínimos sobre las tablas realmente implementadas.
7. Probar desde la API una creación y una lectura del recorrido de negocio; una consulta exitosa en la CLI no verifica la configuración del backend.

No se instala ahora un ORM para evitar comprometer el stack antes de conocer las reglas. Conexión correcta y base con tablas son hitos distintos.

Para comprobar el backend, cuando exista y esté iniciado en el puerto acordado:

```powershell
Invoke-RestMethod -Uri 'http://localhost:8000/health/ready'
```

El resultado esperado es `status: ready`, según el contrato actual. Hoy este comando no funcionará porque aún no hay API implementada.

### Permisos de la conexión

El propietario sirve para preparar el esquema y ejecutar migraciones. La API utilizará un rol de ejecución limitado. Ese rol deberá poder conectarse a la base, usar el esquema y operar sobre las tablas necesarias, sin ser propietario ni poder crear o eliminar el esquema.

Neon distingue los roles creados mediante SQL de los creados con sus herramientas administrativas; estos últimos pueden recibir privilegios elevados. En la CLI 8.11.0 instalada, `neon roles create --help` no muestra `--access`, aunque aparece en documentación más reciente. Por eso no se prescribe aquí ese comando para crear el rol limitado: al integrar se creará mediante SQL y concesiones explícitas, o se usará una CLI actualizada después de verificar sus opciones. [Gestión de roles](https://neon.com/docs/manage/roles).

Las concesiones deben cubrir también las tablas y secuencias futuras creadas por el rol de migraciones. Además, una conexión limitada a tablas no restringe automáticamente las filas de cada gremio: la autorización del backend sigue siendo necesaria.

## 10. Docker y despliegue

| Situación | Configuración |
| --- | --- |
| API local + PostgreSQL local | `DB_HOST=127.0.0.1`, puerto local y configuración del README |
| API en Docker + PostgreSQL del mismo Compose | `DB_HOST=db` y red interna |
| API local o en Docker + Neon | Host real de Neon, puerto 5432 y TLS |

Si el entorno usa Neon, no necesita levantar el servicio `db` para esa aplicación. Tampoco uses el hostname `db`, `localhost` o `127.0.0.1` para apuntar a Neon.

Cuando exista el Compose de aplicaciones, se le pasarán las variables de Neon y se retirará su dependencia del servicio `db` en ese entorno. El Compose actual solo despliega PostgreSQL local; modificar su archivo de entorno no crea ni despliega una API.

En el hosting del backend configura los mismos secretos mediante el panel del proveedor. El frontend solo recibe la URL pública de la API. Ninguna contraseña PostgreSQL debe ir en variables públicas del navegador.

Cambiar el destino de conexión no mueve los datos. Si hubiera datos locales que conservar, habrá que planificar respaldo/restauración y compatibilidad de versiones siguiendo la [guía de operación](operacion.md). Si la base está vacía, bastará aplicar las migraciones aprobadas y los datos de demostración.

## 11. Flujo de equipo para la hackathon

1. Usar `dev` para integrar esquema y API con datos ficticios.
2. Versionar las migraciones en Git y acordar quién las aplica a la rama compartida.
3. Validar el recorrido completo, incluidos reintentos y permisos, antes de preparar una rama de demo.
4. Crear la rama de demo desde un estado conocido o aplicarle migraciones y semillas controladas. Registrar cuál es su URL en el entorno de despliegue.
5. Si una migración cambia en Git, aplicarla explícitamente donde corresponda. Las ramas de Neon no fusionan automáticamente sus cambios de esquema ni datos como un merge de código.

Neon necesita conectividad desde la API. Para la demostración offline del plan, la tablet conserva operaciones localmente y las sincroniza al volver la red; Neon no reemplaza esa cola. Mantener PostgreSQL local como alternativa requiere una configuración de entorno separada y datos preparados, no una conmutación automática.

## 12. Problemas habituales

| Síntoma | Qué revisar |
| --- | --- |
| `neon` no se reconoce | Nueva terminal y ubicación del ejecutable en `PATH` |
| No aparecen proyectos | Cuenta, organización y permisos; utilizar `--org-id` si corresponde |
| Base o rol inexistente | Listados de la rama concreta, sin asumir `brota` o `neondb_owner` |
| Autenticación PostgreSQL fallida | Rol, contraseña y rama; actualizar el secreto de la API si cambió la contraseña |
| Error de TLS/certificado | Modo TLS, host correcto, controlador actualizado y certificados de confianza; no desactivar la verificación como arreglo |
| La CLI conecta y la API no | Carga real de `.env`, nombres de variables y configuración del controlador |
| `relation does not exist` | Base/rama equivocada, esquema distinto o migraciones pendientes |
| Tiempo de espera | Conectividad de salida, estado del endpoint y tiempo de conexión; contemplar reactivación del compute si está suspendido |
| Error con una función de sesión | Revisar compatibilidad con pool y usar conexión directa si la operación la requiere |
| `/health/ready` no responde | Primero iniciar la API; Neon no publica ese endpoint por sí mismo |

No uses `neon init`, `neon bootstrap` o `neon link` como sustitutos de estos pasos sin revisar sus efectos. Por ejemplo, en esta versión `link` puede descargar variables a un `.env`; no hace falta vincular el directorio para los comandos de la guía, que especifican proyecto y rama.

## 13. Qué está comprobado y qué queda pendiente

Se comprobó la versión de CLI, su ayuda local, la estructura del repositorio y la documentación oficial enlazada. No se inició sesión, no se crearon proyectos o ramas, no se leyeron credenciales ni se ejecutaron consultas remotas.

La comprobación real de conexión será el `SELECT` del paso 6. La integración estará terminada cuando el backend cargue sus secretos, pase `/health/ready`, tenga migraciones aplicadas y complete el recorrido de negocio con permisos correctos.
