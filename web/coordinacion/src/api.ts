import type {
  AcuerdoCanal,
  Caso,
  Catalogo,
  Orden,
  OrdenCerrada,
  Recolector,
  Sesion,
} from "./tipos";

const BASE = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(
  /\/$/,
  "",
);

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
    return ["VERSION_CONFLICT", "INVALID_TRANSITION", "NOT_FOUND"].includes(
      this.codigo,
    );
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

export async function pedir<T>(
  metodo: string,
  ruta: string,
  { cuerpo, params, clave }: Opciones = {},
): Promise<T> {
  const url = new URL(BASE + ruta);
  for (const [k, v] of Object.entries(params ?? {}))
    url.searchParams.set(k, String(v));
  const h: Record<string, string> = { Accept: "application/json" };
  if (cuerpo !== undefined) h["Content-Type"] = "application/json";
  if (token) h.Authorization = `Bearer ${token}`;
  if (clave) h["Idempotency-Key"] = clave;

  const tokenSolicitud = token;
  const filas: unknown[] = [];
  while (true) {
    let r: Response;
    try {
      r = await fetch(url, {
        method: metodo,
        headers: h,
        body: cuerpo === undefined ? undefined : JSON.stringify(cuerpo),
      });
    } catch {
      throw new ErrorApi(
        0,
        "RED",
        "No hay conexión con la API de Brota. Revisa el internet o el servidor.",
      );
    }
    const datos = await r.json().catch(() => null);
    if (!r.ok) {
      const e = datos?.error ?? {};
      if (r.status === 401 && token && token === tokenSolicitud) alExpirar();
      throw new ErrorApi(
        r.status,
        e.code ?? "HTTP",
        e.message ?? `Error ${r.status}`,
        e.fields,
      );
    }
    if (!datos || !("data" in datos))
      throw new ErrorApi(
        502,
        "RESPUESTA",
        "El servidor devolvió una respuesta inesperada.",
      );
    if (metodo !== "GET" || !Array.isArray(datos.data) || !datos.pagination)
      return datos.data as T;
    filas.push(...datos.data);
    if (!datos.pagination.has_more) return filas as T;
    const siguiente = Number(datos.pagination.offset) + datos.data.length;
    if (
      siguiente <= Number(url.searchParams.get("offset") || 0) ||
      token !== tokenSolicitud
    )
      throw new ErrorApi(
        409,
        "CONSULTA",
        "La consulta cambió. Actualiza la vista.",
      );
    url.searchParams.set("offset", String(siguiente));
  }
}

function nombreAdjunto(dispo: string | null, respaldo: string): string {
  const citado = /filename="([^"]+)"/.exec(dispo ?? "");
  if (citado?.[1]) return citado[1];
  const simple = /filename=([^;]+)/.exec(dispo ?? "");
  return simple?.[1]?.trim() || respaldo;
}

/** Descarga un archivo con el Bearer ya guardado. No abre la URL sin Authorization. */
export async function descargar(ruta: string, nombre: string): Promise<void> {
  const url = new URL(BASE + ruta);
  const h: Record<string, string> = {};
  if (token) h.Authorization = `Bearer ${token}`;
  let r: Response;
  try {
    r = await fetch(url, { method: "GET", headers: h });
  } catch {
    throw new ErrorApi(
      0,
      "RED",
      "No hay conexión con la API de Brota. Revisa el internet o el servidor.",
    );
  }
  if (!r.ok) {
    const datos = await r.json().catch(() => null);
    const e = datos?.error ?? {};
    if (r.status === 401 && token) alExpirar();
    throw new ErrorApi(
      r.status,
      e.code ?? "HTTP",
      e.message ?? `Error ${r.status}`,
      e.fields,
    );
  }
  const blob = await r.blob();
  const archivo = nombreAdjunto(r.headers.get("Content-Disposition"), nombre);
  const local = URL.createObjectURL(blob);
  const enlace = document.createElement("a");
  enlace.href = local;
  enlace.download = archivo;
  document.body.appendChild(enlace);
  enlace.click();
  enlace.remove();
  URL.revokeObjectURL(local);
}

interface SesionApi {
  token: string;
  expira_en: number;
  cuenta: Sesion["cuenta"];
}

export const api = {
  iniciarSesion: (usuario: string, pin: string) =>
    pedir<SesionApi>("POST", "/v1/auth/sesiones", { cuerpo: { usuario, pin } }),
  catalogo: (gremioId: string) =>
    pedir<Catalogo>("GET", "/v1/catalogos", {
      params: { gremio_id: gremioId },
    }),
  ordenes: (gremioId: string) =>
    pedir<Orden[]>("GET", "/v1/ordenes", {
      params: { gremio_id: gremioId, limit: 100 },
    }),
  recolectores: (gremioId: string) =>
    pedir<Recolector[]>("GET", "/v1/recolectores", {
      params: { gremio_id: gremioId, activo: "true", limit: 100 },
    }),
  /** Asigna o reasigna sin horario: nunca envía `inicio` ni `fin`. */
  asignar: (
    o: Orden,
    datos: { recolector_id: string; forma_aviso: "llamada" | "recado" },
    clave: string,
  ) =>
    pedir<Orden>("POST", `/v1/ordenes/${o.id}/asignacion`, {
      cuerpo: {
        version_esperada: o.version,
        recolector_id: datos.recolector_id,
        forma_aviso: datos.forma_aviso,
      },
      clave,
    }),
  /** Programa o reprograma; el responsable ya está asignado. */
  programar: (
    o: Orden,
    datos: {
      inicio: string;
      fin: string;
      acuerdo_canal: AcuerdoCanal;
      acuerdo_observacion?: string;
    },
    clave: string,
  ) =>
    pedir<Orden>("POST", `/v1/ordenes/${o.id}/programacion`, {
      cuerpo: { version_esperada: o.version, ...datos },
      clave,
    }),
  casos: () => pedir<Caso[]>("GET", "/v1/casos", { params: { limit: 100 } }),
  responderCaso: (c: Caso, respuesta: string, clave: string) =>
    pedir<Caso>("POST", `/v1/casos/${c.id}/atencion`, {
      cuerpo: { version_esperada: c.version, respuesta },
      clave,
    }),
  cerrar: (
    o: Orden,
    datos: {
      resultado: "recogida" | "rechazada";
      materiales_confirmados: string[];
      motivo_rechazo_id?: string;
      observacion?: string;
      ocurrido_at: string;
    },
    clave: string,
  ) =>
    pedir<OrdenCerrada>("POST", `/v1/ordenes/${o.id}/resultado`, {
      cuerpo: { version_esperada: o.version, ...datos },
      clave,
    }),
};
