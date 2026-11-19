import type { Catalogo, Orden, OrdenCerrada, Recolector, Sesion } from "./tipos";

const BASE = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/\/$/, "");

export class ErrorApi extends Error {
  constructor(
    public status: number,
    public codigo: string,
    mensaje: string,
    public campos?: Record<string, string>,
  ) {
    super(mensaje);
  }

  /** Otra persona (o la coordinación por WhatsApp) cambió la orden mientras la mirabas. */
  get ordenCambio(): boolean {
    return ["VERSION_CONFLICT", "INVALID_TRANSITION", "NOT_FOUND"].includes(this.codigo);
  }
}

let token: string | null = null;
let alExpirar: () => void = () => {};

export function fijarToken(t: string | null): void {
  token = t;
}

export function cuandoExpire(fn: () => void): void {
  alExpirar = fn;
}

interface Opciones {
  cuerpo?: unknown;
  params?: Record<string, string | number>;
  clave?: string; // Idempotency-Key
}

async function pedir<T>(metodo: string, ruta: string, { cuerpo, params, clave }: Opciones = {}): Promise<T> {
  const url = new URL(BASE + ruta);
  for (const [k, v] of Object.entries(params ?? {})) url.searchParams.set(k, String(v));
  const h: Record<string, string> = { Accept: "application/json" };
  if (cuerpo !== undefined) h["Content-Type"] = "application/json";
  if (token) h.Authorization = `Bearer ${token}`;
  if (clave) h["Idempotency-Key"] = clave;

  let r: Response;
  try {
    r = await fetch(url, { method: metodo, headers: h, body: cuerpo === undefined ? undefined : JSON.stringify(cuerpo) });
  } catch {
    throw new ErrorApi(0, "RED", "No hay conexión con la API de Brota. Revisa el internet o el servidor.");
  }
  const datos = await r.json().catch(() => null);
  if (!r.ok) {
    const e = datos?.error ?? {};
    if (r.status === 401 && token) alExpirar();
    throw new ErrorApi(r.status, e.code ?? "HTTP", e.message ?? `Error ${r.status}`, e.fields);
  }
  return datos.data as T;
}

interface SesionApi {
  token: string;
  expira_en: number;
  cuenta: Sesion["cuenta"];
}

export const api = {
  iniciarSesion: (usuario: string, pin: string) =>
    pedir<SesionApi>("POST", "/v1/auth/sesiones", { cuerpo: { usuario, pin } }),
  catalogo: (gremioId: string) => pedir<Catalogo>("GET", "/v1/catalogos", { params: { gremio_id: gremioId } }),
  ordenes: () => pedir<Orden[]>("GET", "/v1/ordenes", { params: { limit: 100 } }),
  recolectores: (gremioId: string) =>
    pedir<Recolector[]>("GET", "/v1/recolectores", { params: { gremio_id: gremioId, activo: "true", limit: 100 } }),
  asignar: (
    o: Orden,
    datos: { recolector_id: string; inicio: string | null; fin: string | null; forma_aviso: "llamada" | "recado" },
    clave: string,
  ) => {
    const cuerpo: Record<string, unknown> = {
      version_esperada: o.version,
      recolector_id: datos.recolector_id,
      forma_aviso: datos.forma_aviso,
    };
    if (datos.inicio && datos.fin) Object.assign(cuerpo, { inicio: datos.inicio, fin: datos.fin });
    return pedir<Orden>("POST", `/v1/ordenes/${o.id}/asignacion`, { cuerpo, clave });
  },
  cerrar: (
    o: Orden,
    datos: { resultado: "recogida" | "rechazada"; motivo_rechazo_id?: string; observacion?: string; ocurrido_at: string },
    clave: string,
  ) => pedir<OrdenCerrada>("POST", `/v1/ordenes/${o.id}/resultado`, { cuerpo: { version_esperada: o.version, ...datos }, clave }),
};
