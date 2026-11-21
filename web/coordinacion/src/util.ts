import type { Sesion } from "./tipos";

// ------------------------------------------------------------------ sesión (pestaña actual)

const CLAVE_SESION = "brota.coordinacion.sesion";

export function leerSesion(incluirVencida = false): Sesion | null {
  try {
    const s = JSON.parse(sessionStorage.getItem(CLAVE_SESION) ?? "null") as Sesion | null;
    return s && (incluirVencida || s.expira > Date.now()) ? s : null;
  } catch {
    return null;
  }
}

export function guardarSesion(s: Sesion | null): void {
  try {
    if (s) sessionStorage.setItem(CLAVE_SESION, JSON.stringify(s));
    else sessionStorage.removeItem(CLAVE_SESION);
  } catch {
    /* sin almacenamiento: la sesión dura lo que la pestaña */
  }
}

// ------------------------------------------------------------------ claves de idempotencia

/** UUID v4. `crypto.randomUUID` solo existe en https/localhost; la tablet puede entrar por la IP local. */
export function claveNueva(): string {
  if (typeof crypto.randomUUID === "function") return crypto.randomUUID();
  const b = crypto.getRandomValues(new Uint8Array(16));
  b[6] = (b[6] & 0x0f) | 0x40;
  b[8] = (b[8] & 0x3f) | 0x80;
  const h = [...b].map((x) => x.toString(16).padStart(2, "0")).join("");
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`;
}

/** Misma operación reintentada (mismo cuerpo) = misma clave; si cambia el cuerpo, clave nueva. */
export function claveParaEnvio() {
  let ultimo = "";
  let clave = "";
  return (cuerpo: unknown): string => {
    const s = JSON.stringify(cuerpo);
    if (s !== ultimo) {
      ultimo = s;
      clave = claveNueva();
    }
    return clave;
  };
}

// ------------------------------------------------------------------ horas en Bogotá

const ZONA = "America/Bogota";
const OFFSET = "-05:00"; // Colombia no cambia de horario
const fmtDia = new Intl.DateTimeFormat("en-CA", { timeZone: ZONA, year: "numeric", month: "2-digit", day: "2-digit" });
const fmtHora = new Intl.DateTimeFormat("en-US", { timeZone: ZONA, hour: "numeric", minute: "2-digit", hour12: true });
const fmtFecha = new Intl.DateTimeFormat("es-CO", { timeZone: ZONA, day: "numeric", month: "short" });

const HORARIOS: [number, number][] = [
  [8, 10],
  [10, 12],
  [14, 16],
  [16, 18],
];

function h12(h: number): string {
  if (h === 12) return "12pm";
  return h > 12 ? `${h - 12}pm` : `${h}am`;
}

function hora(d: Date): string {
  const p = fmtHora.formatToParts(d);
  const v = (t: string) => p.find((x) => x.type === t)?.value ?? "";
  const min = v("minute");
  return `${v("hour")}${min === "00" ? "" : ":" + min}${v("dayPeriod").toLowerCase()}`;
}

export function dia(d: Date): string {
  const hoy = new Date();
  const k = fmtDia.format(d);
  if (k === fmtDia.format(hoy)) return "Hoy";
  if (k === fmtDia.format(new Date(hoy.getTime() + 864e5))) return "Mañana";
  if (k === fmtDia.format(new Date(hoy.getTime() - 864e5))) return "Ayer";
  return fmtFecha.format(d);
}

export interface Franja {
  id: string;
  titulo: string;
  inicio: string | null;
  fin: string | null;
}

/** Franjas de hoy y mañana que aún sirven (les queda al menos media hora), más «sin hora fija». */
export function franjas(ahora = new Date()): Franja[] {
  const salida: Franja[] = [];
  for (const [desfase, etiqueta] of [
    [0, "Hoy"],
    [1, "Mañana"],
  ] as const) {
    const fecha = fmtDia.format(new Date(ahora.getTime() + desfase * 864e5));
    for (const [a, b] of HORARIOS) {
      const inicio = `${fecha}T${String(a).padStart(2, "0")}:00:00${OFFSET}`;
      const fin = `${fecha}T${String(b).padStart(2, "0")}:00:00${OFFSET}`;
      if (new Date(fin).getTime() - ahora.getTime() < 30 * 60e3) continue;
      salida.push({ id: `${fecha}-${a}`, titulo: `${etiqueta} ${h12(a)}–${h12(b)}`, inicio, fin });
    }
  }
  salida.push({ id: "SIN", titulo: "Sin hora fija", inicio: null, fin: null });
  return salida;
}

export function textoFranja(inicio: string | null, fin: string | null): string {
  if (!inicio || !fin) return "Sin hora fija";
  const i = new Date(inicio);
  return `${dia(i)} ${hora(i)}–${hora(new Date(fin))}`;
}

export function diaDe(iso: string | null): "hoy" | "manana" | "otro" | "sin" {
  if (!iso) return "sin";
  const d = dia(new Date(iso));
  return d === "Hoy" ? "hoy" : d === "Mañana" ? "manana" : "otro";
}

export function hace(iso: string, ahora = Date.now()): string {
  const min = Math.round((ahora - new Date(iso).getTime()) / 60000);
  if (min < 1) return "ahora";
  if (min < 60) return `hace ${min} min`;
  const h = Math.round(min / 60);
  if (h < 24) return `hace ${h} h`;
  const d = new Date(iso);
  return `${dia(d)} ${hora(d)}`;
}

export function puntos(valor: string | null): string {
  if (!valor) return "0";
  return valor.includes(".") ? valor.replace(/\.?0+$/, "") : valor;
}
