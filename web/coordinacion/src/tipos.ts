// Formas de la API de Brota que usa el panel (ver docs/contrato-api.md).

export type EstadoOrden = "nueva" | "asignada" | "recogida" | "rechazada";

export interface Asignacion {
  recolector_id: string;
  recolector_nombre: string;
  inicio: string | null;
  fin: string | null;
  forma_aviso: "llamada" | "recado";
  vigente_desde: string;
}

export interface Resultado {
  resultado: "recogida" | "rechazada";
  motivo_rechazo_id: string | null;
  motivo_rechazo_nombre: string | null;
  observacion: string | null;
  ocurrido_at: string;
  confirmado_at: string;
}

export interface Orden {
  id: string;
  created_at: string;
  version: number;
  estado: EstadoOrden;
  gremio_id: string;
  gremio_nombre: string;
  solicitud_id: string;
  codigo_pasaporte: string;
  tipo_servicio_ids: string[];
  asignacion: Asignacion | null;
  reasignaciones: number;
  resultado: Resultado | null;
  unidad_id: string;
  ubicacion_operativa: string;
  torre_id: string | null;
  contacto_nombre: string | null;
  observacion: string | null;
}

export interface OrdenCerrada extends Orden {
  evaluacion_puntos: "acreditada" | "no_aplica" | "pendiente" | "requiere_revision";
  puntos_otorgados: string | null;
}

export interface Recolector {
  id: string;
  gremio_id: string;
  nombre: string;
  telefono_contacto: string | null;
  activo: boolean;
}

export interface ItemCatalogo {
  id: string;
  codigo: string;
  nombre: string;
  gremio_id?: string | null;
}

export interface Catalogo {
  gremios: ItemCatalogo[];
  tipos_servicio: ItemCatalogo[];
  motivos_rechazo: ItemCatalogo[];
}

export interface Permiso {
  rol: string;
  gremio_id: string | null;
}

export interface Sesion {
  token: string;
  expira: number; // epoch ms
  cuenta: { id: string; nombre: string; permisos: Permiso[] };
}
