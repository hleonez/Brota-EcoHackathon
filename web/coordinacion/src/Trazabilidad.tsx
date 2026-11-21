/**
 * Trazabilidad (Administración): tablero Kanban de las solicitudes de todos los gremios, desde que
 * el vecino escribe a Brisa hasta el cierre, y la historia completa de cada una en una ficha.
 * Solo lectura: asignar, programar y cerrar sigue siendo de la coordinación de cada gremio (RN-01).
 */
import { useEffect, useMemo, useState, type CSSProperties } from "react";
import {
  BotonDescarga, actorPorTipo, descargarCSV, diaBogota, horaBogota, nombreEvento, nombresEvento, periodoMes,
} from "./AdminExtra";
import { Modal } from "./Dialogos";
import { Icono } from "./Iconos";
import { Espera, fechaBogota, useDatos } from "./portal";
import type { Catalogo } from "./tipos";

const enc = encodeURIComponent;

interface Tarjeta {
  orden_id: string; solicitud_id: string; codigo_pasaporte: string; estado: string;
  gremio_id: string; gremio_nombre: string; canal_origen: string;
  creada_at: string; en_estado_desde: string; ubicacion: string; contacto_nombre: string | null;
  que: string[]; preferencia_horaria: string | null; observacion: string | null;
  recolector_nombre: string | null; inicio: string | null; fin: string | null; reasignaciones: number;
  motivo_rechazo: string | null; cerrada_at: string | null; avisos_pendientes: number; avisos_fallidos: number;
}
interface Tablero {
  tarjetas: Tarjeta[];
  resumen: { por_estado: Record<string, number>; total: number; truncado: boolean; ventana_dias_cerradas: number | null };
}
type Paso =
  | { clase: "evento"; tipo: string; ocurrido_at: string; actor_tipo: string; actor_nombre: string | null; datos: Record<string, unknown> }
  | { clase: "aviso"; tipo: string; ocurrido_at: string; destino: "vecino" | "coordinacion" | "sin_destino"; estado: string; intentos: number; texto: string | null };
interface Historia extends Tarjeta {
  tipo_generador: string | null;
  otras_ordenes: { orden_id: string; gremio_nombre: string; estado: string }[];
  pesajes: { codigo: string; estado: string; fecha_medicion: string }[];
  puntos_otorgados: string;
  linea: Paso[];
}

/** Columnas del tablero, en el orden del recorrido. */
const columnas: { estado: string; titulo: string; ayuda: string; tono: string; icono: string }[] = [
  { estado: "nueva", titulo: "Sin asignar", ayuda: "Llegó por WhatsApp y espera recolector", tono: "turquesa", icono: "bandeja" },
  { estado: "asignada", titulo: "Asignadas", ayuda: "Con recolector, falta acordar la hora", tono: "amarillo", icono: "recolectores" },
  { estado: "programada", titulo: "Programadas", ayuda: "Con día y hora de visita", tono: "lila", icono: "calendario" },
  { estado: "recogida", titulo: "Recogidas", ayuda: "Material recibido, puntos abonados", tono: "verde", icono: "check" },
  { estado: "rechazada", titulo: "Rechazadas", ayuda: "No se pudo llevar el material", tono: "rojo", icono: "motivos" },
  { estado: "cancelada", titulo: "Canceladas", ayuda: "El vecino la canceló", tono: "gris", icono: "cerrar" },
];
const columnaDe = Object.fromEntries(columnas.map((c) => [c.estado, c]));

const nombresAviso: Record<string, string> = {
  nueva_orden: "Brisa avisó a la coordinación",
  asignacion: "Brisa le dijo al vecino quién pasa",
  recoleccion_confirmada: "Brisa le agradeció y contó sus puntos",
  rechazo_educativo: "Brisa le explicó por qué no se llevó",
  orden_cancelada: "Brisa avisó la cancelación a la coordinación",
};
const estadoAviso: Record<string, [string, string]> = {
  enviado: ["Entregado ✓✓", "estado-ok"],
  pendiente: ["En cola", "estado-alerta"],
  en_envio: ["Enviando…", "estado-alerta"],
  fallido: ["No se pudo entregar", "estado-error"],
  descartado: ["Descartado", "estado-apagado"],
};
const destinos = { vecino: "al vecino", coordinacion: "a la coordinación", sin_destino: "" } as const;

/** «hace 5 min», «hace 3 h», «hace 2 días». */
function hace(iso: string, ahora = Date.now()) {
  const min = Math.max(0, Math.round((ahora - Date.parse(iso)) / 60000));
  if (min < 1) return "ahora";
  if (min < 60) return `hace ${min} min`;
  const h = Math.round(min / 60);
  if (h < 24) return `hace ${h} h`;
  const d = Math.round(h / 24);
  return `hace ${d} ${d === 1 ? "día" : "días"}`;
}
const fechaCorta = (iso: string) =>
  new Intl.DateTimeFormat("es-CO", { timeZone: "America/Bogota", day: "numeric", month: "short" }).format(new Date(iso));
function franja(inicio: string | null, fin: string | null) {
  if (!inicio) return null;
  return `${fechaCorta(inicio)} · ${horaBogota(inicio)}${fin ? "–" + horaBogota(fin) : ""}`;
}

/** Lo que merece la atención de la administración en cada tarjeta. */
function alertas(t: Tarjeta, ahora = Date.now()): string[] {
  const horas = (ahora - Date.parse(t.en_estado_desde)) / 3600000;
  const lista: string[] = [];
  if (t.estado === "nueva" && horas >= 24) lista.push(`Espera recolector ${hace(t.en_estado_desde, ahora)}`);
  if (t.estado === "asignada" && horas >= 48) lista.push("Sin hora acordada");
  if (t.estado === "programada" && t.fin && Date.parse(t.fin) < ahora) lista.push("La visita ya pasó y no se ha cerrado");
  if (t.avisos_fallidos > 0) lista.push("Un aviso de WhatsApp no llegó");
  return lista;
}

type Ventana = "activas" | "mes" | "anterior";
const ventanas: [Ventana, string][] = [["activas", "Activas y últimos 30 días"], ["mes", "Este mes"], ["anterior", "Mes pasado"]];

export function Trazabilidad() {
  const [ventana, setVentana] = useState<Ventana>("activas");
  const [gremio, setGremio] = useState("");
  const [q, setQ] = useState("");
  const [busqueda, setBusqueda] = useState("");
  const [abierta, setAbierta] = useState<string | null>(null);
  const [mostrar, setMostrar] = useState<Record<string, number>>({});
  const [ahora, setAhora] = useState(() => Date.now());
  const cat = useDatos<Catalogo>("/v1/catalogos");

  useEffect(() => {
    const id = setTimeout(() => setBusqueda(q.trim()), 300);
    return () => clearTimeout(id);
  }, [q]);

  const ruta = useMemo(() => {
    const p = new URLSearchParams();
    if (ventana !== "activas") {
      const periodo = periodoMes(ventana === "mes" ? 0 : -1);
      p.set("desde", periodo.desde);
      p.set("hasta", periodo.hasta);
    }
    if (gremio) p.set("gremio_id", gremio);
    if (busqueda) p.set("q", busqueda);
    const texto = p.toString();
    return "/v1/trazabilidad" + (texto ? "?" + texto : "");
  }, [ventana, gremio, busqueda]);
  const tablero = useDatos<Tablero>(ruta);
  const { recargar } = tablero;

  // El tablero se refresca solo cada 30 s: lo que pasa en WhatsApp aparece sin recargar.
  useEffect(() => {
    const id = setInterval(() => { recargar(); setAhora(Date.now()); }, 30000);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ruta]);

  const d = tablero.datos;
  const porEstado = useMemo(() => {
    const grupos: Record<string, Tarjeta[]> = Object.fromEntries(columnas.map((c) => [c.estado, []]));
    for (const t of d?.tarjetas ?? []) (grupos[t.estado] ??= []).push(t);
    return grupos;
  }, [d]);
  const conAlerta = (d?.tarjetas ?? []).filter((t) => alertas(t, ahora).length > 0).length;
  const enCurso = (d?.resumen.por_estado.asignada ?? 0) + (d?.resumen.por_estado.programada ?? 0);

  function exportar() {
    descargarCSV("trazabilidad", ["Código", "Estado", "Gremio", "Ubicación", "Vecino", "Qué", "Recolector", "Visita", "Creada", "En el estado desde", "Motivo de rechazo"],
      (d?.tarjetas ?? []).map((t) => [t.codigo_pasaporte, columnaDe[t.estado]?.titulo ?? t.estado, t.gremio_nombre, t.ubicacion,
        t.contacto_nombre, t.que.join(", "), t.recolector_nombre, franja(t.inicio, t.fin), fechaBogota(new Date(t.creada_at)),
        fechaBogota(new Date(t.en_estado_desde)), t.motivo_rechazo]));
  }

  return (
    <section className="traza" aria-labelledby="traza-titulo">
      <div className="traza-cabeza eco-tarjeta">
        <div className="traza-flujo" aria-hidden="true">
          <span><Icono nombre="conversaciones" />WhatsApp</span><i />
          <span><Icono nombre="bandeja" />Coordinación</span><i />
          <span><Icono nombre="recolectores" />Recolector</span><i />
          <span><Icono nombre="check" />Cierre</span>
        </div>
        <div className="lista-encabezado">
          <h2 id="traza-titulo">Recorrido de las solicitudes</h2>
          <div className="lista-herramientas">
            <label className="buscador-mini"><Icono nombre="buscar" /><span className="visually-hidden">Buscar por código o ubicación</span>
              <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="BR-00012 o Torre 3" /></label>
            <label className="filtro-select"><span className="visually-hidden">Gremio</span>
              <select value={gremio} onChange={(e) => setGremio(e.target.value)}>
                <option value="">Todos los gremios</option>
                {(cat.datos?.gremios ?? []).map((g) => <option key={g.id} value={g.id}>{g.nombre}</option>)}
              </select>
            </label>
            <button type="button" className="btn" onClick={() => { recargar(); setAhora(Date.now()); }}><Icono nombre="historial" />Actualizar</button>
            <BotonDescarga onClick={exportar}>CSV</BotonDescarga>
          </div>
        </div>
        <div className="selector-periodo" role="group" aria-label="Periodo">
          {ventanas.map(([k, t]) => (
            <button key={k} type="button" aria-pressed={ventana === k} onClick={() => setVentana(k)}>{t}</button>
          ))}
        </div>
        {d && (
          <ul className="traza-resumen">
            <li className="tono-turquesa"><strong>{d.resumen.por_estado.nueva ?? 0}</strong><span>esperan recolector</span></li>
            <li className="tono-lila"><strong>{enCurso}</strong><span>en camino</span></li>
            <li className="tono-verde"><strong>{d.resumen.por_estado.recogida ?? 0}</strong><span>recogidas</span></li>
            <li className={conAlerta ? "tono-rojo" : "tono-gris"}><strong>{conAlerta}</strong><span>necesitan atención</span></li>
          </ul>
        )}
      </div>

      {!d ? <Espera error={tablero.error} reintentar={recargar} /> : (
        <>
          {d.resumen.truncado && <p className="nota-privacidad"><Icono nombre="reportes" />Se muestran las 500 más recientes. Filtra por gremio o periodo para ver el resto.</p>}
          <div className="kanban" role="list" aria-label="Solicitudes por estado">
            {columnas.map((c, i) => {
              const tarjetas = porEstado[c.estado] ?? [];
              const limite = mostrar[c.estado] ?? 12;
              return (
                <section key={c.estado} className={"kanban-col tono-" + c.tono} role="listitem" aria-label={c.titulo}
                  style={{ "--i": i } as CSSProperties}>
                  <header className="kanban-col-cabeza">
                    <span className="kanban-col-icono" aria-hidden="true"><Icono nombre={c.icono} /></span>
                    <span className="kanban-col-texto"><strong>{c.titulo}</strong><small>{c.ayuda}</small></span>
                    <span className="kanban-col-cuenta">{d.resumen.por_estado[c.estado] ?? tarjetas.length}</span>
                  </header>
                  <div className="kanban-col-cuerpo">
                    {tarjetas.length === 0 ? <p className="kanban-vacio">Nada por aquí.</p> : tarjetas.slice(0, limite).map((t, n) => (
                      <TarjetaKanban key={t.orden_id} t={t} n={n} ahora={ahora} abrir={() => setAbierta(t.orden_id)} />
                    ))}
                    {tarjetas.length > limite && (
                      <button type="button" className="btn btn-sm kanban-mas"
                        onClick={() => setMostrar((m) => ({ ...m, [c.estado]: limite + 12 }))}>
                        Ver {Math.min(12, tarjetas.length - limite)} más de {tarjetas.length - limite}
                      </button>
                    )}
                  </div>
                </section>
              );
            })}
          </div>
          <p className="chat-privacidad"><Icono nombre="piloto" />Solo lectura para Administración: la coordinación de cada gremio asigna y cierra. Sin celulares; el vecino aparece por su nombre.</p>
        </>
      )}
      {abierta && <FichaOrden ordenId={abierta} cerrar={() => setAbierta(null)} abrirOtra={setAbierta} />}
    </section>
  );
}

function TarjetaKanban({ t, n, ahora, abrir }: { t: Tarjeta; n: number; ahora: number; abrir: () => void }) {
  const avisos = alertas(t, ahora);
  const visita = franja(t.inicio, t.fin);
  return (
    <button type="button" className={"kanban-tarjeta" + (avisos.length ? " con-alerta" : "")} onClick={abrir}
      style={{ "--n": Math.min(n, 10) } as CSSProperties} aria-label={`Ver la historia de ${t.codigo_pasaporte}`}>
      <span className="kanban-tarjeta-fila">
        <strong className="kanban-codigo">{t.codigo_pasaporte}</strong>
        <span className="kanban-gremio">{t.gremio_nombre}</span>
      </span>
      <span className="kanban-linea"><Icono nombre="ubicacion" />{t.ubicacion}</span>
      {t.contacto_nombre && <span className="kanban-linea"><Icono nombre="cuenta" />{t.contacto_nombre}</span>}
      {t.que.length > 0 && (
        <span className="kanban-que">{t.que.slice(0, 3).map((x) => <span key={x}>{x}</span>)}{t.que.length > 3 && <span>+{t.que.length - 3}</span>}</span>
      )}
      {t.recolector_nombre && <span className="kanban-linea"><Icono nombre="recolectores" />{t.recolector_nombre}{t.reasignaciones > 0 && ` · reasignada ${t.reasignaciones}×`}</span>}
      {visita && <span className="kanban-linea"><Icono nombre="calendario" />{visita}</span>}
      {t.motivo_rechazo && <span className="kanban-linea kanban-motivo"><Icono nombre="motivos" />{t.motivo_rechazo}</span>}
      {avisos.map((a) => <span key={a} className="kanban-alerta"><Icono nombre="campana" />{a}</span>)}
      <span className="kanban-pie">
        <span>{t.canal_origen === "whatsapp" ? "🌱 Por WhatsApp" : t.canal_origen}</span>
        <time dateTime={t.en_estado_desde} title={new Date(t.en_estado_desde).toLocaleString("es-CO", { timeZone: "America/Bogota" })}>{hace(t.en_estado_desde, ahora)}</time>
      </span>
    </button>
  );
}

const pasos = ["nueva", "asignada", "programada", "cierre"] as const;

function FichaOrden({ ordenId, cerrar, abrirOtra }: { ordenId: string; cerrar: () => void; abrirOtra: (id: string) => void }) {
  const h = useDatos<Historia>(`/v1/trazabilidad/${enc(ordenId)}`);
  const d = h.datos;
  const final = d && ["recogida", "rechazada", "cancelada"].includes(d.estado);
  const alcanzado = d ? (final ? 3 : pasos.indexOf(d.estado as (typeof pasos)[number])) : -1;
  return (
    <Modal titulo={d ? `Solicitud ${d.codigo_pasaporte}` : "Historia de la solicitud"} onCerrar={cerrar}>
      {!d ? <Espera error={h.error} reintentar={h.recargar} /> : (
        <div className="traza-ficha">
          <div className="traza-ficha-cabeza">
            <span className={"registro-estado traza-estado tono-" + (columnaDe[d.estado]?.tono ?? "gris")}>
              <Icono nombre={columnaDe[d.estado]?.icono ?? "hoja"} />{columnaDe[d.estado]?.titulo ?? d.estado}
            </span>
            <span className="registro-dato">{d.gremio_nombre}</span>
            <span className="registro-dato">Creada {fechaCorta(d.creada_at)} · {horaBogota(d.creada_at)}</span>
          </div>

          <ol className="traza-pasos" aria-label="Avance">
            {pasos.map((p, i) => {
              const titulo = p === "cierre" ? (final ? columnaDe[d.estado].titulo.replace(/s$/, "") : "Cierre") : columnaDe[p].titulo.replace(/s$/, "");
              return (
                <li key={p} className={(i < alcanzado ? "hecho" : i === alcanzado ? "actual" : "") + (p === "cierre" && final ? " tono-" + columnaDe[d.estado].tono : "")}
                  aria-current={i === alcanzado ? "step" : undefined}>
                  <span className="traza-paso-punto">{i < alcanzado || (i === alcanzado && final) ? <Icono nombre="check" /> : i + 1}</span>
                  <span>{p === "nueva" ? "Recibida" : titulo}</span>
                </li>
              );
            })}
          </ol>

          <dl className="traza-datos">
            <div><dt>Ubicación</dt><dd>{d.ubicacion}</dd></div>
            <div><dt>Vecino</dt><dd>{d.contacto_nombre ?? "—"}{d.tipo_generador ? ` · ${d.tipo_generador}` : ""}</dd></div>
            <div><dt>Qué entrega</dt><dd>{d.que.join(", ") || "—"}</dd></div>
            <div><dt>Prefiere</dt><dd>{d.preferencia_horaria ?? "—"}</dd></div>
            <div><dt>Recolector</dt><dd>{d.recolector_nombre ?? "Sin asignar"}</dd></div>
            <div><dt>Visita</dt><dd>{franja(d.inicio, d.fin) ?? "Sin hora"}</dd></div>
            {d.observacion && <div className="ancho"><dt>Nota del vecino</dt><dd>{d.observacion}</dd></div>}
            {d.motivo_rechazo && <div className="ancho"><dt>Motivo del rechazo</dt><dd>{d.motivo_rechazo}</dd></div>}
            {d.estado === "recogida" && <div><dt>Puntos abonados</dt><dd>{Number(d.puntos_otorgados).toLocaleString("es-CO")}</dd></div>}
            {d.pesajes.length > 0 && <div><dt>Pesajes</dt><dd>{d.pesajes.map((p) => `${p.codigo} (${p.estado})`).join(", ")}</dd></div>}
          </dl>

          {d.otras_ordenes.length > 0 && (
            <div className="traza-otras">
              <span>La misma solicitud también va a:</span>
              {d.otras_ordenes.map((o) => (
                <button key={o.orden_id} type="button" className="registro-dato traza-otra" onClick={() => abrirOtra(o.orden_id)}>
                  <span className={"punto tono-" + (columnaDe[o.estado]?.tono ?? "gris")} aria-hidden="true" />{o.gremio_nombre} · {columnaDe[o.estado]?.titulo ?? o.estado}
                </button>
              ))}
            </div>
          )}

          <h3 className="traza-subtitulo">Paso a paso</h3>
          <ol className="linea-tiempo traza-linea">
            {d.linea.map((x, n) => {
              const dia = diaBogota(x.ocurrido_at);
              const nuevoDia = n === 0 || diaBogota(d.linea[n - 1].ocurrido_at) !== dia;
              return (
                <li key={n} style={{ "--n": n } as CSSProperties}>
                  {nuevoDia && <p className="linea-tiempo-dia">{dia}</p>}
                  {x.clase === "evento" ? <PasoEvento x={x} /> : <PasoAviso x={x} />}
                </li>
              );
            })}
          </ol>
        </div>
      )}
    </Modal>
  );
}

function PasoEvento({ x }: { x: Extract<Paso, { clase: "evento" }> }) {
  const quien = x.actor_nombre ?? actorPorTipo[x.actor_tipo] ?? x.actor_tipo;
  const recolector = typeof x.datos.recolector_nombre === "string" ? x.datos.recolector_nombre : null;
  const motivo = typeof x.datos.motivo === "string" ? x.datos.motivo : null;
  return (
    <div className="linea-tiempo-item">
      <span className="registro-avatar tono-verde" aria-hidden="true"><Icono nombre={nombresEvento[x.tipo]?.[1] ?? "hoja"} /></span>
      <div className="registro-texto">
        <strong>{x.tipo === "orden_creada" ? "Entró a la bandeja del gremio" : nombreEvento(x.tipo)}</strong>
        <div className="registro-datos">
          <span className={"registro-dato" + (quien === "Brisa" ? " es-brisa" : "")}>{quien === "Brisa" ? "🌱 " : ""}{quien}</span>
          {recolector && <span className="registro-dato">→ {recolector}</span>}
          {motivo && <span className="registro-dato">{motivo}</span>}
        </div>
      </div>
      <time dateTime={x.ocurrido_at}>{horaBogota(x.ocurrido_at)}</time>
    </div>
  );
}

function PasoAviso({ x }: { x: Extract<Paso, { clase: "aviso" }> }) {
  const [texto, clase] = estadoAviso[x.estado] ?? [x.estado, "estado-apagado"];
  return (
    <div className="linea-tiempo-item traza-aviso">
      <span className="registro-avatar tono-turquesa" aria-hidden="true"><Icono nombre="conversaciones" /></span>
      <div className="registro-texto">
        <strong>{nombresAviso[x.tipo] ?? `Aviso ${destinos[x.destino]}`}</strong>
        {x.texto && <p className="chat-burbuja de-brisa traza-burbuja"><span className="chat-autor">Brisa 🌱 {destinos[x.destino]}</span>{x.texto}</p>}
        <div className="registro-datos">
          <span className={"registro-estado " + clase}>{texto}</span>
          {x.intentos > 1 && <span className="registro-dato">{x.intentos} intentos</span>}
        </div>
      </div>
      <time dateTime={x.ocurrido_at}>{horaBogota(x.ocurrido_at)}</time>
    </div>
  );
}
