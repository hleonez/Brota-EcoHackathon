# Panel de coordinación

Panel web para la coordinadora de cada gremio (Asorescatar, Huerta Ecorazón), pensado para tablet.
React 19 + Vite + TypeScript, sin librerías de componentes. Habla solo con la API de Brota.

| Sección | Qué hace |
| --- | --- |
| **Bandeja** | Solicitudes nuevas (la más antigua primero) y asignadas por cerrar. Se actualiza sola cada 15 s y avisa cuando llega una nueva. |
| **Asignar** | Recolector del gremio (con su teléfono), franja de hoy o mañana (o sin hora fija) y cómo se le avisa (llamada o recado). Brisa le escribe al vecino quién pasa. |
| **Rutas de hoy** | Paradas pendientes por recolector, ordenadas por franja, con su teléfono para llamar. Filtros: hoy, mañana, sin hora. |
| **Cerrar** | ✅ Recogida (el vecino recibe sus puntos) o ❌ Rechazada con motivo del gremio (el vecino recibe un consejo). También se puede reasignar. |
| **Historial** | Órdenes cerradas, con totales del día. |

Pendiente: pesajes (kg por material y lectura del tiquete), modo sin conexión y registro asistido.

## Arrancar en desarrollo

Requisitos: Node 20 o superior y la API corriendo.

```powershell
cd web/coordinacion
npm install
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
