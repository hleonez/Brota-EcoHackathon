# Brota · EcoConecta Villas de San Pablo

Frontend React y TypeScript para la comunidad, los colectivos de recolección y la Fundación Santo Domingo. La distribución incluye Bootstrap Grid 5.3.3 y los logos oficiales. El servicio lee datos de FastAPI y conserva los controles de acceso en el servidor.

| Perfil | Recorrido |
| --- | --- |
| Hogares y negocios | Guía de separación, preparación y horarios. Solicitudes y seguimiento mediante Brisa en WhatsApp. Configura el número oficial con VITE_WHATSAPP_NUMERO en formato internacional, solo dígitos. |
| Huerta y Asorescatar | Inicio, bandeja, asignación con o sin franja, programación, rutas, cierre, pasaporte, avisos, equipo, pesajes y reportes agregados del colectivo. |
| Fundación | Hogares participantes, órdenes por estado, valor estimado y materiales por método de medición. Filtros de fechas y colectivo. El panel solicita reportes agregados. |
| Administración | Cuentas y PIN, recolectores, unidades productivas, registro asistido, materiales, motivos, contenidos, equivalencias y versiones de reglas. |

## Compatibilidad con el servidor

Comunidad y Administración se integran con la API de develop, commit f03226a.

- La guía consulta contenidos públicos por tema mediante `GET /v1/contenidos-educativos`.
- Administración crea cuentas de huertero y reciclador vinculadas a trabajadores activos sin cuenta. El gremio se toma del trabajador.
- Educación admite título, texto, tema y publicación. El panel de administración lista borradores, publicados y retirados con `GET /v1/contenidos-educativos/gestion`, y edita, publica, retira o reactiva con la versión esperada. La guía pública sigue mostrando solo las publicaciones vigentes.
- Piloto elige participante y unidad mediante `GET /v1/participantes`. Las fechas se interpretan en Bogotá. Cambiar una fecha conserva el vencimiento original cuando el día no cambia. Quitar el vencimiento y revocar son acciones explícitas.
- Los formularios recargan la lista ante conflictos de versión. Las respuestas de formularios desmontados no cierran otro editor.

La vista operativa de las cuentas de trabajador depende de la integración del frontend de Operación. Unidades y registro asistido leen `GET /v1/unidades/gestion`, reservada a administración; el directorio `GET /v1/unidades` sigue siendo de coordinación. El servidor conserva la validación de permisos, transiciones y puntos.

## Arrancar en desarrollo

Requisitos: Node 22.12 o superior y la API corriendo.

```powershell
cd web/coordinacion
npm ci
Copy-Item .env.example .env.local
npm run dev
```

Abre `http://localhost:3000` y entra con una cuenta de coordinación (en el seed: `coord-reciclaje` o
`coord-huerta`, con el PIN de `SEED_PIN`).

- `VITE_API_URL` (en `.env.local`): URL de la API. Vite la lee al arrancar `npm run dev` y la deja fija
  al compilar. Es pública: nunca pongas secretos aquí. En este equipo la API local está en
  `http://localhost:8010`.
- La API debe permitir el origen del panel en `CORS_ALLOWED_ORIGINS` (ya incluye `http://localhost:3000`).
- Revisar tipos: `npm run check`. Compilar: `npm run build` (sale en `dist/`, archivos estáticos).

## Usarlo desde una tablet en la misma red

1. Arranca con `npm run dev -- --host` y abre en la tablet `http://<IP-del-PC>:3000`.
2. En `.env.local`, `VITE_API_URL=http://<IP-del-PC>:<puerto de la API>` (reinicia `npm run dev`).
3. Agrega `http://<IP-del-PC>:3000` a `CORS_ALLOWED_ORIGINS` de la API y reiníciala.

Para producción se sirve `dist/` detrás de HTTPS en el mismo dominio que la API.

## Cómo funciona

- **Sesión:** `POST /v1/auth/sesiones` con usuario y PIN devuelve un JWT; se guarda solo en la pestaña
  (`sessionStorage`). Si la API responde 401, vuelve a pedir el PIN.
- **Escrituras:** cada asignación o cierre lleva `version_esperada` y una `Idempotency-Key`. Si se
  reintenta lo mismo (por ejemplo, se cayó la red), no se duplica. Si otra persona cambió la orden, el
  panel lo dice y recarga la bandeja.
- **WhatsApp:** la coordinadora recibe por WhatsApp solo la alerta «🆕 Nueva solicitud…» que la
  manda al panel. Con `COORDINACION_POR_WHATSAPP=true` en el bot también puede asignar y cerrar desde
  el chat (respaldo si no hay tablet).

```text
src/
├─ api.ts        Cliente de la API (token, errores, idempotencia)
├─ App.tsx       Ingreso con usuario y PIN
├─ Panel.tsx     Estructura, datos y actualización automática
├─ Vistas.tsx    Bandeja, Rutas e Historial
├─ Dialogos.tsx  Asignar y cerrar (recogida o rechazo)
├─ util.ts       Sesión, claves, franjas y horas en Bogotá
└─ estilos.css   Estilos (tablet primero, modo oscuro)
```

Consulta las [convenciones comunes](../README.md) y el [contrato de la API](../../docs/contrato-api.md).


## Recorridos de diseño

| Referencias | Navegación |
| --- | --- |
| A01–A04 | Inicio de sesión, acceso restringido, sesión vencida y Mi cuenta. |
| H01–H15 | Inicio de huerta, bandeja, detalle, asignación, programación, reasignación, cierre, cancelación, rutas, baldes, historial, indicadores, mensajes y equipo. |
| R01–R16 | Las mismas operaciones para reciclaje, con registro de pesajes, consulta de registros y Tiquete Vivo. |
| D01–D19 | Inicio de administración, cuentas, recolectores, piloto, unidades, registro asistido, reglas, educación, catálogos y estado del sistema. |

La cancelación desde coordinación informa el canal disponible para el vecino. El módulo de piloto requiere las rutas del plan de API. El editor publica contenido nuevo, recupera borradores y retirados, y guarda los cambios de un contenido ya existente.
