/**
 * Secciones de Administración que no son una lista genérica:
 * tablero de inicio, participantes, precios, liga de torres, reportes (descargas), actividad,
 * conversaciones de Brisa (estilo WhatsApp, con privacidad) y datos del programa.
 */
import { useEffect, useMemo, useRef, useState, type CSSProperties, type ReactNode } from "react";
import { pedir } from "./api";
import { Modal } from "./Dialogos";
import { Campo, Formulario } from "./Formulario";
import { Icono } from "./Iconos";
import Indicadores from "./Indicadores";
import { Paginada } from "./Paginacion";
import { Espera, Estado, fechaBogota, numero, useDatos } from "./portal";

// ------------------------------------------------------------------ utilidades

const enc = encodeURIComponent;

/** Mes calendario en Bogotá (UTC−5 fijo): 0 = este mes, −1 = el anterior. */
export function periodoMes(desplazamiento = 0, meses = 1) {
  const partes = new Intl.DateTimeFormat("en-CA", { timeZone: "America/Bogota", year: "numeric", month: "2-digit" })
    .formatToParts(new Date());
  const anio = Number(partes.find((p) => p.type === "year")!.value);
  const mes = Number(partes.find((p) => p.type === "month")!.value) - 1 + desplazamiento;
  const inicio = new Date(Date.UTC(anio, mes - (meses - 1), 1));
  const fin = new Date(Date.UTC(anio, mes + 1, 1));
  const iso = (d: Date) => `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, "0")}-01T00:00:00-05:00`;
  const nombre = new Intl.DateTimeFormat("es-CO", { month: "long", year: "numeric", timeZone: "UTC" }).format(new Date(Date.UTC(anio, mes, 1)));
  return { desde: iso(inicio), hasta: iso(fin), nombre };
}

type Periodo = "mes" | "anterior" | "trimestre";
const periodos: Record<Periodo, () => ReturnType<typeof periodoMes>> = {
  mes: () => periodoMes(0),
  anterior: () => periodoMes(-1),
  trimestre: () => ({ ...periodoMes(0, 3), nombre: "los últimos 3 meses" }),
};

function SelectorPeriodo({ valor, cambiar }: { valor: Periodo; cambiar: (p: Periodo) => void }) {
  return (
    <div className="selector-periodo" role="group" aria-label="Periodo">
      {([["mes", "Este mes"], ["anterior", "Mes pasado"], ["trimestre", "3 meses"]] as const).map(([k, t]) => (
        <button key={k} type="button" aria-pressed={valor === k} onClick={() => cambiar(k)}>{t}</button>
      ))}
    </div>
  );
}

/** CSV con «;» (Excel en español) y BOM para que las tildes se vean bien. */
export function descargarCSV(nombre: string, encabezados: string[], filas: (string | number | null | undefined)[][]) {
  const celda = (v: string | number | null | undefined) => {
    const t = v === null || v === undefined ? "" : String(v);
    return /[;"\n]/.test(t) ? `"${t.replaceAll('"', '""')}"` : t;
  };
  const texto = "﻿" + [encabezados, ...filas].map((f) => f.map(celda).join(";")).join("\r\n");
  const url = URL.createObjectURL(new Blob([texto], { type: "text/csv;charset=utf-8" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = nombre.endsWith(".csv") ? nombre : nombre + ".csv";
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function BotonDescarga({ onClick, children }: { onClick: () => void | Promise<void>; children: ReactNode }) {
  const [ocupado, setOcupado] = useState(false);
  return (
    <button type="button" className="btn boton-descarga" disabled={ocupado}
      onClick={async () => { setOcupado(true); try { await onClick(); } finally { setOcupado(false); } }}>
      <Icono nombre="descargar" />{ocupado ? "Preparando…" : children}
    </button>
  );
}

/** Cuenta de 0 al valor al aparecer (se apaga con «reducir movimiento»). */
function useConteo(valor: number) {
  const [mostrado, setMostrado] = useState(0);
  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) { setMostrado(valor); return; }
    let id = 0;
    const inicio = performance.now();
    const paso = (t: number) => {
      const avance = Math.min(1, (t - inicio) / 800);
      setMostrado(valor * (1 - Math.pow(1 - avance, 3)));
      if (avance < 1) id = requestAnimationFrame(paso);
    };
    id = requestAnimationFrame(paso);
    return () => cancelAnimationFrame(id);
  }, [valor]);
  return mostrado;
}

function iniciales(texto: string) {
  return texto.split(/\s+/).filter((p) => /^[\p{L}\p{N}]/u.test(p)).slice(0, 2).map((p) => p[0]).join("").toUpperCase() || "·";
}

const horaBogota = (iso: string) =>
  new Intl.DateTimeFormat("es-CO", { timeZone: "America/Bogota", hour: "numeric", minute: "2-digit" }).format(new Date(iso));
const diaBogota = (iso: string) =>
  new Intl.DateTimeFormat("es-CO", { timeZone: "America/Bogota", weekday: "long", day: "numeric", month: "long" }).format(new Date(iso));

// ------------------------------------------------------------------ tablero de inicio

interface ResumenPeriodo {
  ordenes_por_estado: Record<string, number>;
  resultados: { recogidas: number; rechazadas: number };
  tasa_rechazo_ordenes: number | null;
  kg_aceptados: string;
  kg_rechazados: string;
  hogares_participantes: number;
  valor_estimado: string | null;
  materiales: { material_id: string; nombre: string; kg_aceptados: string; kg_rechazados: string }[];
}

export const estadosOrden: [string, string, string][] = [
  ["nueva", "Nuevas", "turquesa"],
  ["asignada", "Asignadas", "amarillo"],
  ["programada", "Programadas", "lila"],
  ["recogida", "Recogidas", "verde"],
  ["rechazada", "Rechazadas", "rojo"],
  ["cancelada", "Canceladas", "gris"],
];

function Kpi({ icono, valor, texto, tono, decimales = 0, sufijo = "" }: {
  icono: string; valor: number; texto: string; tono: string; decimales?: number; sufijo?: string;
}) {
  const v = useConteo(valor);
  return (
    <div className={"kpi-clay tono-" + tono}>
      <span className="kpi-clay-icono" aria-hidden="true"><Icono nombre={icono} /></span>
      <span className="kpi-clay-valor">
        {v.toLocaleString("es-CO", { maximumFractionDigits: decimales, minimumFractionDigits: 0 })}{sufijo}
      </span>
      <span className="kpi-clay-texto">{texto}</span>
    </div>
  );
}

function BarraEstados({ porEstado }: { porEstado: Record<string, number> }) {
  const total = estadosOrden.reduce((s, [k]) => s + (porEstado[k] ?? 0), 0);
  return (
    <div className="barra-estados">
      <div className="barra-estados-pista" role="img"
        aria-label={estadosOrden.map(([k, t]) => `${t}: ${porEstado[k] ?? 0}`).join(", ")}>
        {total > 0 && estadosOrden.map(([k, , tono]) => (porEstado[k] ?? 0) > 0 && (
          <span key={k} className={"barra-estados-tramo tono-" + tono}
            style={{ "--ancho": `${((porEstado[k] ?? 0) / total) * 100}%` } as CSSProperties} />
        ))}
      </div>
      <ul className="barra-estados-leyenda">
        {estadosOrden.map(([k, t, tono]) => (
          <li key={k}><span className={"punto tono-" + tono} aria-hidden="true" />{t}<strong>{porEstado[k] ?? 0}</strong></li>
        ))}
      </ul>
    </div>
  );
}

export function TableroInicio({ navegar }: { navegar: (id: string) => void }) {
  const p = useMemo(() => periodoMes(0), []);
  const r = useDatos<ResumenPeriodo>(`/v1/reportes/resumen?desde=${enc(p.desde)}&hasta=${enc(p.hasta)}`);
  const d = r.datos;
  const total = d ? Object.values(d.ordenes_por_estado).reduce((a, b) => a + b, 0) : 0;
  const porAtender = d ? (d.ordenes_por_estado.nueva ?? 0) + (d.ordenes_por_estado.asignada ?? 0) + (d.ordenes_por_estado.programada ?? 0) : 0;
  return (
    <section className="tablero" aria-labelledby="tablero-titulo">
      <div className="tablero-cabeza">
        <div>
          <h2 id="tablero-titulo">Así va {p.nombre}</h2>
          <p>Solicitudes, recolecciones y participación del programa en el mes.</p>
        </div>
        <button type="button" className="btn" onClick={() => navegar("Reportes")}><Icono nombre="reportes" />Ver reportes</button>
      </div>
      {!d ? <Espera error={r.error} reintentar={r.recargar} /> : (
        <>
          <div className="tablero-kpis">
            <Kpi icono="bandeja" valor={total} texto="Solicitudes del mes" tono="verde" />
            <Kpi icono="reloj" valor={porAtender} texto="Por atender" tono="amarillo" />
            <Kpi icono="check" valor={d.resultados.recogidas} texto="Recolecciones hechas" tono="turquesa" />
            <Kpi icono="pesajes" valor={Number(d.kg_aceptados)} texto="Kilos aprovechados" tono="lila" decimales={1} sufijo=" kg" />
            <Kpi icono="casa" valor={d.hogares_participantes} texto="Hogares participantes" tono="verde" />
            <Kpi icono="motivos" valor={(d.tasa_rechazo_ordenes ?? 0) * 100} texto="Tasa de rechazo" tono="amarillo" decimales={1} sufijo="%" />
          </div>
          <div className="tablero-estados">
            <h3>Estado de las solicitudes del mes</h3>
            <BarraEstados porEstado={d.ordenes_por_estado} />
          </div>
        </>
      )}
    </section>
  );
}

// ------------------------------------------------------------------ participantes

interface Participante { id: string; nombre: string; unidades: { id: string; tipo: string; etiqueta: string }[] }
interface Habilitacion { id: string; participante_id: string; activo: boolean; vigente_desde: string | null; vigente_hasta: string | null }

function habilitado(h: Habilitacion, ahora = Date.now()) {
  return h.activo && (!h.vigente_desde || Date.parse(h.vigente_desde) <= ahora) && (!h.vigente_hasta || Date.parse(h.vigente_hasta) > ahora);
}

export function Participantes({ navegar }: { navegar: (id: string) => void }) {
  const lista = useDatos<Participante[]>("/v1/participantes?limit=100");
  const habs = useDatos<Habilitacion[]>("/v1/piloto/habilitaciones");
  const [q, setQ] = useState("");
  const conPiloto = new Set((habs.datos ?? []).filter((h) => habilitado(h)).map((h) => h.participante_id));
  const filas = (lista.datos ?? []).filter((p) =>
    [p.nombre, ...p.unidades.map((u) => u.etiqueta)].join(" ").toLocaleLowerCase("es").includes(q.trim().toLocaleLowerCase("es")));
  return (
    <section className="eco-tarjeta">
      <div className="lista-encabezado">
        <h2>Vecinos registrados</h2>
        <div className="lista-herramientas">
          <label className="buscador-mini"><Icono nombre="buscar" /><span className="visually-hidden">Buscar participante</span>
            <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Buscar por nombre o unidad" /></label>
          <BotonDescarga onClick={() => descargarCSV("participantes", ["Nombre", "Unidades", "Tipo", "Piloto"],
            (lista.datos ?? []).map((p) => [p.nombre, p.unidades.map((u) => u.etiqueta).join(" | "),
              [...new Set(p.unidades.map((u) => u.tipo))].join(", "), conPiloto.has(p.id) ? "Habilitado" : "Sin habilitar"]))}>
            CSV
          </BotonDescarga>
        </div>
      </div>
      <p className="nota-privacidad"><Icono nombre="piloto" />Por privacidad, el celular de cada vecino no se muestra en el panel.</p>
      {!lista.datos ? <Espera error={lista.error} reintentar={lista.recargar} /> : filas.length === 0 ? (
        <div className="vacio-clay"><p>{q ? `Nada coincide con «${q}».` : "Todavía no hay vecinos registrados."}</p></div>
      ) : (
        <Paginada key={q} items={filas} porPagina={8} etiqueta="participantes">
          {(pagina) => (
            <div className="tabla-envoltura">
              <table className="tabla-clay">
                <thead><tr><th>Participante</th><th>Unidades</th><th>Piloto</th><th><span className="visually-hidden">Acciones</span></th></tr></thead>
                <tbody>
                  {pagina.map((p, n) => (
                    <tr key={p.id} style={{ "--n": n } as CSSProperties}>
                      <td><span className="celda-persona"><span className="registro-avatar tono-verde" aria-hidden="true">{iniciales(p.nombre)}</span><strong>{p.nombre}</strong></span></td>
                      <td><span className="registro-datos">{p.unidades.length ? p.unidades.map((u) => (
                        <span key={u.id} className="registro-dato">{u.tipo === "negocio" ? "🏪 " : "🏠 "}{u.etiqueta}</span>
                      )) : <span className="registro-dato">Sin unidad</span>}</span></td>
                      <td>{conPiloto.has(p.id)
                        ? <span className="registro-estado estado-ok"><Icono nombre="check" />Habilitado</span>
                        : <span className="registro-estado estado-apagado">Sin habilitar</span>}</td>
                      <td className="celda-acciones">
                        <button type="button" className="btn btn-sm registro-editar" onClick={() => navegar("Piloto")}>
                          <Icono nombre="piloto" />{conPiloto.has(p.id) ? "Ver piloto" : "Habilitar"}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Paginada>
      )}
    </section>
  );
}

// ------------------------------------------------------------------ precios

interface Precio { id: string; material_id: string; precio_kg: string; moneda: string; vigente_desde: string; vigente_hasta: string | null }
interface Material { id: string; nombre: string; activo?: boolean }

export function Precios() {
  const precios = useDatos<Precio[]>("/v1/configuracion?tipo=precios");
  const materiales = useDatos<Material[]>("/v1/materiales?limit=100");
  const [abierto, setAbierto] = useState(false);
  const nombres = new Map((materiales.datos ?? []).map((m) => [m.id, m.nombre]));
  const ahora = Date.now();
  // la versión vigente de cada material es la más reciente que ya empezó y no ha terminado
  const vigentes = new Set<string>();
  for (const m of new Set((precios.datos ?? []).map((p) => p.material_id))) {
    const actual = (precios.datos ?? [])
      .filter((p) => p.material_id === m && Date.parse(p.vigente_desde) <= ahora && (!p.vigente_hasta || Date.parse(p.vigente_hasta) > ahora))
      .sort((a, b) => b.vigente_desde.localeCompare(a.vigente_desde))[0];
    if (actual) vigentes.add(actual.id);
  }
  const filas = [...(precios.datos ?? [])].sort((a, b) =>
    (nombres.get(a.material_id) ?? "").localeCompare(nombres.get(b.material_id) ?? "", "es") || b.vigente_desde.localeCompare(a.vigente_desde));
  const pesos = (v: string) => Number(v).toLocaleString("es-CO", { style: "currency", currency: "COP", maximumFractionDigits: 0 });
  return (
    <section className="eco-tarjeta">
      <div className="lista-encabezado">
        <h2>Precio por kilo</h2>
        <div className="lista-herramientas">
          <button type="button" className="btn primario" onClick={() => setAbierto(true)}><Icono nombre="nuevo" />Nuevo precio</button>
        </div>
      </div>
      <p className="nota-privacidad"><Icono nombre="hoja" />Cada cambio crea una versión nueva: los pesajes viejos conservan el precio con el que se valoraron. Es un valor estimado, no un pago certificado.</p>
      {!precios.datos ? <Espera error={precios.error} reintentar={precios.recargar} /> : filas.length === 0 ? (
        <div className="vacio-clay"><img src="/panel/monedas.webp" alt="" /><p>Aún no hay precios. Crea el primero.</p></div>
      ) : (
        <Paginada items={filas} porPagina={8} etiqueta="precios">
          {(pagina) => (
            <div className="tabla-envoltura">
              <table className="tabla-clay">
                <thead><tr><th>Material</th><th className="num">Precio por kg</th><th>Desde</th><th>Estado</th></tr></thead>
                <tbody>
                  {pagina.map((p, n) => {
                    const futuro = Date.parse(p.vigente_desde) > ahora;
                    return (
                      <tr key={p.id} style={{ "--n": n } as CSSProperties}>
                        <td><span className="celda-persona"><span className="registro-avatar tono-amarillo" aria-hidden="true"><Icono nombre="materiales" /></span><strong>{nombres.get(p.material_id) ?? "Material"}</strong></span></td>
                        <td className="num"><strong>{pesos(p.precio_kg)}</strong></td>
                        <td>{fechaBogota(new Date(p.vigente_desde))}</td>
                        <td>{vigentes.has(p.id)
                          ? <span className="registro-estado estado-ok"><Icono nombre="check" />Vigente</span>
                          : futuro ? <span className="registro-estado estado-alerta"><Icono nombre="reloj" />Programado</span>
                          : <span className="registro-estado estado-apagado">Histórico</span>}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </Paginada>
      )}
      {abierto && (
        <Modal titulo="Nuevo precio por kilo" onCerrar={() => setAbierto(false)}>
          <Formulario titulo="Nuevo precio por kilo" accion="Guardar precio"
            preparar={(v) => ({
              ruta: "precios-material",
              cuerpo: {
                material_id: v.material_id,
                precio_kg: v.precio_kg,
                ...(v.vigente_desde ? { vigente_desde: v.vigente_desde + "T00:00:00-05:00" } : {}),
              },
            })}
            alGuardar={() => { setAbierto(false); precios.recargar(); }}>
            <Campo nombre="material_id" titulo="Material"
              opciones={(materiales.datos ?? []).filter((m) => m.activo !== false).map((m) => [m.id, m.nombre])} />
            <Campo nombre="precio_kg" titulo="Precio por kilo (COP)" tipo="number" min={0} step="1" />
            <Campo nombre="vigente_desde" titulo="Vigente desde (vacío = desde hoy)" tipo="date" opcional />
          </Formulario>
        </Modal>
      )}
    </section>
  );
}

// ------------------------------------------------------------------ liga de torres

interface Liga {
  descripcion_formula: string;
  torres: { torre_id: string; torre_nombre: string; hogares_participantes: number; viviendas_base: number;
    porcentaje_participacion: string; kg_aceptados_atribuidos: string; posicion: number }[];
}

function useConjunto() {
  const c = useDatos<{ id: string; nombre: string }[]>("/v1/conjuntos");
  return c.datos?.[0];
}

export function LigaTorres() {
  const [periodo, setPeriodo] = useState<Periodo>("mes");
  const p = periodos[periodo]();
  const conjunto = useConjunto();
  const liga = useDatos<Liga>(conjunto ? `/v1/liga?conjunto_id=${conjunto.id}&desde=${enc(p.desde)}&hasta=${enc(p.hasta)}` : "");
  const torres = liga.datos?.torres ?? [];
  const podio = torres.slice(0, 3);
  const medallas = ["oro", "plata", "bronce"];
  return (
    <>
      <section className="eco-tarjeta">
        <div className="lista-encabezado">
          <h2>Ranking de {p.nombre}</h2>
          <div className="lista-herramientas">
            <SelectorPeriodo valor={periodo} cambiar={setPeriodo} />
            <BotonDescarga onClick={() => descargarCSV(`liga-torres-${periodo}`, ["Posición", "Torre", "Hogares participantes", "Viviendas", "% participación", "Kg aceptados"],
              torres.map((t) => [t.posicion, t.torre_nombre, t.hogares_participantes, t.viviendas_base, t.porcentaje_participacion, t.kg_aceptados_atribuidos]))}>CSV</BotonDescarga>
          </div>
        </div>
        {!liga.datos ? <Espera error={liga.error} reintentar={liga.recargar} /> : torres.length === 0 ? (
          <div className="vacio-clay"><img src="/panel/estrella.webp" alt="" /><p>Aún no hay participación en este periodo.</p></div>
        ) : (
          <>
            <ol className="podio">
              {podio.map((t, i) => (
                <li key={t.torre_id} className={"podio-puesto puesto-" + medallas[i]}>
                  <span className="podio-medalla" aria-hidden="true">{i + 1}</span>
                  <strong>{t.torre_nombre}</strong>
                  <span className="podio-porcentaje">{numero(t.porcentaje_participacion)}%</span>
                  <small>{t.hogares_participantes} de {t.viviendas_base} hogares</small>
                </li>
              ))}
            </ol>
            <Paginada items={torres} porPagina={6} etiqueta="torres">
              {(pagina) => (
                <div className="tabla-envoltura">
                  <table className="tabla-clay">
                    <thead><tr><th className="num">#</th><th>Torre</th><th>Participación</th><th className="num">Hogares</th><th className="num">Kg</th></tr></thead>
                    <tbody>
                      {pagina.map((t, n) => (
                        <tr key={t.torre_id} style={{ "--n": n } as CSSProperties}>
                          <td className="num"><strong>{t.posicion}</strong></td>
                          <td><strong>{t.torre_nombre}</strong></td>
                          <td>
                            <span className="progreso" role="img" aria-label={`${t.porcentaje_participacion}% de participación`}>
                              <span className="progreso-barra" style={{ "--ancho": `${Math.min(100, Number(t.porcentaje_participacion))}%` } as CSSProperties} />
                            </span>
                            <span className="progreso-texto">{numero(t.porcentaje_participacion)}%</span>
                          </td>
                          <td className="num">{t.hogares_participantes} / {t.viviendas_base}</td>
                          <td className="num">{numero(t.kg_aceptados_atribuidos)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </Paginada>
            <p className="nota-privacidad"><Icono nombre="puntos" />{liga.datos.descripcion_formula}</p>
          </>
        )}
      </section>
    </>
  );
}

// ------------------------------------------------------------------ reportes (descargas + impacto)

export function Reportes() {
  const [periodo, setPeriodo] = useState<Periodo>("mes");
  const conjunto = useConjunto();
  const p = periodos[periodo]();
  return (
    <>
      <section className="eco-tarjeta descargas">
        <div className="lista-encabezado">
          <h2>Descargar reportes</h2>
          <SelectorPeriodo valor={periodo} cambiar={setPeriodo} />
        </div>
        <p className="nota-privacidad"><Icono nombre="descargar" />Archivos CSV que abre Excel. Periodo: {p.nombre}. No incluyen celulares ni direcciones.</p>
        <div className="descargas-botones">
          <BotonDescarga onClick={async () => {
            const r = await pedir<ResumenPeriodo>("GET", `/v1/reportes/resumen?desde=${enc(p.desde)}&hasta=${enc(p.hasta)}`);
            descargarCSV(`resumen-${periodo}`, ["Indicador", "Valor"], [
              ...estadosOrden.map(([k, t]) => [`Solicitudes ${t.toLowerCase()}`, r.ordenes_por_estado[k] ?? 0]),
              ["Kg aceptados", r.kg_aceptados], ["Kg rechazados", r.kg_rechazados],
              ["Hogares participantes", r.hogares_participantes],
              ["Tasa de rechazo (%)", ((r.tasa_rechazo_ordenes ?? 0) * 100).toFixed(1)],
              ["Valor estimado (COP)", r.valor_estimado ?? ""],
              ...r.materiales.map((m) => [`Kg aceptados · ${m.nombre}`, m.kg_aceptados]),
            ]);
          }}>Resumen del periodo</BotonDescarga>
          <BotonDescarga onClick={async () => {
            if (!conjunto) return;
            const l = await pedir<Liga>("GET", `/v1/liga?conjunto_id=${conjunto.id}&desde=${enc(p.desde)}&hasta=${enc(p.hasta)}`);
            descargarCSV(`liga-torres-${periodo}`, ["Posición", "Torre", "Hogares participantes", "Viviendas", "% participación", "Kg aceptados"],
              l.torres.map((t) => [t.posicion, t.torre_nombre, t.hogares_participantes, t.viviendas_base, t.porcentaje_participacion, t.kg_aceptados_atribuidos]));
          }}>Liga de torres</BotonDescarga>
          <BotonDescarga onClick={async () => {
            const e = await pedir<Evento[]>("GET", `/v1/eventos?limit=100&desde=${enc(p.desde)}&hasta=${enc(p.hasta)}`);
            descargarCSV(`actividad-${periodo}`, ["Fecha", "Hora", "Evento", "Quién"],
              e.map((x) => [fechaBogota(new Date(x.ocurrido_at)), horaBogota(x.ocurrido_at), nombreEvento(x.tipo), x.actor_nombre ?? actorPorTipo[x.actor_tipo] ?? x.actor_tipo]));
          }}>Actividad</BotonDescarga>
        </div>
      </section>
      <Indicadores />
    </>
  );
}

// ------------------------------------------------------------------ actividad (auditoría)

interface Evento {
  id: string; tipo: string; ocurrido_at: string; actor_tipo: string; actor_nombre: string | null;
  solicitud_id: string | null; orden_id: string | null; pesaje_id: string | null; datos: Record<string, unknown>;
}

const nombresEvento: Record<string, [string, string]> = {
  orden_creada: ["Nueva solicitud de recolección", "bandeja"],
  orden_asignada: ["Solicitud asignada a un recolector", "recolectores"],
  orden_reasignada: ["Solicitud reasignada", "recolectores"],
  orden_cancelada: ["Solicitud cancelada", "cerrar"],
  orden_programada: ["Visita programada", "calendario"],
  orden_recogida: ["Recolección hecha", "check"],
  orden_rechazada: ["Recolección rechazada", "motivos"],
  solicitud_creada: ["Vecino pidió una recolección", "bandeja"],
  caso_creado: ["Reporte de un vecino", "reportes"],
  caso_atendido: ["Reporte respondido", "check"],
  cuenta_creada: ["Cuenta del panel creada", "cuentas"],
  cuenta_actualizada: ["Cuenta del panel actualizada", "llave"],
  participante_registrado: ["Vecino registrado por WhatsApp", "registro asistido"],
  participante_registrado_asistido: ["Vecino registrado en el panel", "registro asistido"],
  piloto_habilitado: ["Vecino habilitado en el piloto", "piloto"],
  piloto_actualizado: ["Habilitación del piloto cambiada", "piloto"],
  pesaje_borrador_creado: ["Pesaje en borrador", "pesajes"],
  pesaje_borrador_actualizado: ["Pesaje en borrador actualizado", "pesajes"],
  pesaje_confirmado: ["Pesaje confirmado", "pesajes"],
  pesaje_corregido: ["Pesaje corregido", "pesajes"],
  pesaje_anulado: ["Pesaje anulado", "cerrar"],
  entrega_directa_registrada: ["Entrega directa registrada", "entregas"],
  material_creado: ["Material agregado", "materiales"],
  precio_versionado: ["Nuevo precio por kilo", "equivalencias"],
  regla_incentivo_versionada: ["Nueva regla de puntos", "puntos"],
  recolector_creado: ["Recolector agregado", "recolectores"],
  unidad_actualizada: ["Unidad actualizada", "unidades"],
  solicitud_eliminacion: ["Vecino pidió borrar sus datos", "motivos"],
  programa_actualizado: ["Datos del programa actualizados", "sistema"],
};
function nombreEvento(tipo: string) {
  return nombresEvento[tipo]?.[0] ?? tipo.replaceAll("_", " ").replace(/^\w/, (c) => c.toUpperCase());
}
const actorPorTipo: Record<string, string> = { servicio_bot: "Brisa", servicio: "Brisa", participante: "Vecino", operador: "Panel", sistema: "Sistema", no_registrado: "Vecino nuevo" };

export function Actividad() {
  const [tipo, setTipo] = useState("");
  const tipos = useDatos<string[]>("/v1/eventos/tipos");
  const eventos = useDatos<Evento[]>("/v1/eventos?limit=100" + (tipo ? "&tipo=" + enc(tipo) : ""));
  return (
    <section className="eco-tarjeta">
      <div className="lista-encabezado">
        <h2>Qué pasó y quién lo hizo</h2>
        <div className="lista-herramientas">
          <label className="filtro-select"><span className="visually-hidden">Tipo de evento</span>
            <select value={tipo} onChange={(e) => setTipo(e.target.value)}>
              <option value="">Todos los eventos</option>
              {(tipos.datos ?? []).map((t) => <option key={t} value={t}>{nombreEvento(t)}</option>)}
            </select>
          </label>
          <BotonDescarga onClick={() => descargarCSV("actividad", ["Fecha", "Hora", "Evento", "Quién"],
            (eventos.datos ?? []).map((x) => [fechaBogota(new Date(x.ocurrido_at)), horaBogota(x.ocurrido_at), nombreEvento(x.tipo), x.actor_nombre ?? actorPorTipo[x.actor_tipo] ?? x.actor_tipo]))}>CSV</BotonDescarga>
        </div>
      </div>
      {!eventos.datos ? <Espera error={eventos.error} reintentar={eventos.recargar} /> : eventos.datos.length === 0 ? (
        <div className="vacio-clay"><p>Todavía no hay actividad registrada.</p></div>
      ) : (
        <Paginada key={tipo} items={eventos.datos} porPagina={10} etiqueta="actividad">
          {(pagina) => (
            <ol className="linea-tiempo">
              {pagina.map((e, n) => {
                const dia = diaBogota(e.ocurrido_at);
                const nuevoDia = n === 0 || diaBogota(pagina[n - 1].ocurrido_at) !== dia;
                const quien = e.actor_nombre ?? actorPorTipo[e.actor_tipo] ?? e.actor_tipo;
                return (
                  <li key={e.id} style={{ "--n": n } as CSSProperties}>
                    {nuevoDia && <p className="linea-tiempo-dia">{dia}</p>}
                    <div className="linea-tiempo-item">
                      <span className="registro-avatar tono-verde" aria-hidden="true"><Icono nombre={nombresEvento[e.tipo]?.[1] ?? "hoja"} /></span>
                      <div className="registro-texto">
                        <strong>{nombreEvento(e.tipo)}</strong>
                        <div className="registro-datos">
                          <span className={"registro-dato" + (quien === "Brisa" ? " es-brisa" : "")}>{quien === "Brisa" ? "🌱 " : ""}{quien}</span>
                          {typeof e.datos?.codigo === "string" && <span className="registro-dato">{e.datos.codigo}</span>}
                        </div>
                      </div>
                      <time dateTime={e.ocurrido_at}>{horaBogota(e.ocurrido_at)}</time>
                    </div>
                  </li>
                );
              })}
            </ol>
          )}
        </Paginada>
      )}
    </section>
  );
}

// ------------------------------------------------------------------ conversaciones de Brisa

interface Chat {
  clave: string; nombre: string; celular_enmascarado: string; ultimo_texto: string; ultimo_at: string;
  ultima_direccion: "entrante" | "saliente"; total: number; registrado: boolean;
}
interface Mensaje { id: string; direccion: "entrante" | "saliente"; tipo: string; texto: string; created_at: string }

function Burbujas({ chat }: { chat: Chat }) {
  const desde = Math.max(0, chat.total - 100);
  const mensajes = useDatos<Mensaje[]>(`/v1/conversaciones/${chat.clave}/mensajes?limit=100&offset=${desde}`);
  const fondo = useRef<HTMLDivElement>(null);
  const { recargar } = mensajes;
  useEffect(() => {
    const id = setInterval(recargar, 15000);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chat.clave]);
  useEffect(() => {
    fondo.current?.scrollTo({ top: fondo.current.scrollHeight });
  }, [mensajes.datos]);
  return (
    <div className="chat-mensajes" ref={fondo} aria-live="polite">
      {!mensajes.datos ? <Espera error={mensajes.error} reintentar={mensajes.recargar} /> : mensajes.datos.map((m, i) => {
        const dia = diaBogota(m.created_at);
        const nuevoDia = i === 0 || diaBogota(mensajes.datos![i - 1].created_at) !== dia;
        return (
          <div key={m.id} className="chat-fila">
            {nuevoDia && <p className="chat-dia"><span>{dia}</span></p>}
            <div className={"chat-burbuja " + (m.direccion === "saliente" ? "de-brisa" : "del-vecino") + " tipo-" + m.tipo}>
              {m.direccion === "saliente" && <span className="chat-autor">Brisa 🌱</span>}
              <p>{m.texto}</p>
              <time dateTime={m.created_at}>{horaBogota(m.created_at)}{m.direccion === "saliente" && " ✓✓"}</time>
            </div>
          </div>
        );
      })}
    </div>
  );
}

export function Conversaciones() {
  const chats = useDatos<Chat[]>("/v1/conversaciones?limit=100");
  const [q, setQ] = useState("");
  const [clave, setClave] = useState<string | null>(null);
  const { recargar } = chats;
  useEffect(() => {
    const id = setInterval(recargar, 20000);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const filtrados = (chats.datos ?? []).filter((c) => c.nombre.toLocaleLowerCase("es").includes(q.trim().toLocaleLowerCase("es")));
  const actual = chats.datos?.find((c) => c.clave === clave);
  return (
    <section className={"chat" + (actual ? " con-chat" : "")} aria-label="Conversaciones de Brisa">
      <aside className="chat-lista">
        <div className="chat-lista-cabeza">
          <strong>Chats</strong>
          <button type="button" className="btn btn-sm" onClick={chats.recargar}>Actualizar</button>
        </div>
        <label className="buscador-mini"><Icono nombre="buscar" /><span className="visually-hidden">Buscar chat</span>
          <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Buscar vecino" /></label>
        {!chats.datos ? <Espera error={chats.error} reintentar={chats.recargar} /> : filtrados.length === 0 ? (
          <p className="chat-vacio">{q ? "Ningún chat coincide." : "Aún no hay conversaciones guardadas. Brisa las registra desde esta versión."}</p>
        ) : (
          <ul>
            {filtrados.map((c) => (
              <li key={c.clave}>
                <button type="button" className="chat-item" aria-current={c.clave === clave ? "true" : undefined} onClick={() => setClave(c.clave)}>
                  <span className={"registro-avatar " + (c.registrado ? "tono-verde" : "tono-lila")} aria-hidden="true">{iniciales(c.nombre)}</span>
                  <span className="chat-item-texto">
                    <strong>{c.nombre}</strong>
                    <small>{c.ultima_direccion === "saliente" ? "Brisa: " : ""}{c.ultimo_texto}</small>
                  </span>
                  <span className="chat-item-meta"><time dateTime={c.ultimo_at}>{horaBogota(c.ultimo_at)}</time><span className="chat-contador">{c.total}</span></span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </aside>
      <div className="chat-panel">
        {actual ? (
          <>
            <header className="chat-cabeza">
              <button type="button" className="chat-volver" onClick={() => setClave(null)} aria-label="Volver a los chats"><Icono nombre="chevron" /></button>
              <span className={"registro-avatar " + (actual.registrado ? "tono-verde" : "tono-lila")} aria-hidden="true">{iniciales(actual.nombre)}</span>
              <span className="chat-cabeza-texto">
                <strong>{actual.nombre}</strong>
                <small>{actual.celular_enmascarado} · {actual.registrado ? "Registrado" : "Sin registrar"}</small>
              </span>
            </header>
            <Burbujas key={actual.clave} chat={actual} />
            <p className="chat-pie"><Icono nombre="piloto" />Solo lectura. Brisa responde sola; la coordinación atiende desde la Bandeja y los Reportes.</p>
          </>
        ) : (
          <div className="chat-bienvenida">
            <img src="/panel/vecina.webp" alt="" />
            <strong>Conversaciones de Brisa</strong>
            <p>Elige un chat para ver qué le preguntó cada vecino y qué le respondió Brisa.</p>
          </div>
        )}
      </div>
      <p className="chat-privacidad"><Icono nombre="piloto" />Privacidad: solo administración ve los chats, los celulares van enmascarados y los mensajes se borran a los 30 días. De audios y fotos solo queda el texto.</p>
    </section>
  );
}

// ------------------------------------------------------------------ datos del programa

const camposPrograma: [string, string, string][] = [
  ["nombre_programa", "Nombre del programa", "Aparece en la guía para hogares y negocios."],
  ["horario_atencion", "Horario de atención", "Cuándo responde la coordinación."],
  ["dias_recoleccion", "Días de recolección", "Cómo se organizan las rutas."],
  ["telefono_contacto", "Teléfono de contacto", "Línea pública del programa (no personal)."],
  ["correo_contacto", "Correo de contacto", "Correo público del programa."],
  ["mensaje_bienvenida", "Saludo de Brisa", "Si lo escribes, Brisa saluda así a los vecinos. Vacío: saludo por defecto."],
];

export function Programa() {
  const programa = useDatos<Record<string, string>>("/v1/programa");
  const [version, setVersion] = useState(0);
  return (
    <div className="row g-3">
      <div className="col-12 col-xl-7">
        {!programa.datos ? (
          <section className="eco-tarjeta"><h2>Datos del programa</h2><Espera error={programa.error} reintentar={programa.recargar} /></section>
        ) : (
          <Formulario key={version} titulo="Datos del programa" accion="Guardar cambios"
            preparar={(v) => ({ ruta: "programa", metodo: "PATCH", cuerpo: Object.fromEntries(camposPrograma.map(([k]) => [k, v[k] ?? ""])) })}
            alGuardar={() => { programa.recargar(); setVersion((x) => x + 1); }}>
            {camposPrograma.map(([k, t, ayuda]) => (
              <div key={k} className="campo-con-ayuda">
                <Campo nombre={k} titulo={t} valorInicial={programa.datos![k] ?? ""} opcional maxLength={500}
                  tipo={k === "correo_contacto" ? "email" : k === "telefono_contacto" ? "tel" : "text"} />
                <small>{ayuda}</small>
              </div>
            ))}
          </Formulario>
        )}
      </div>
      <div className="col-12 col-xl-5">
        <section className="eco-tarjeta vista-previa">
          <h2>Así lo ve el vecino</h2>
          <div className="chat-mensajes es-previa">
            <div className="chat-burbuja del-vecino"><p>Hola</p></div>
            <div className="chat-burbuja de-brisa"><span className="chat-autor">Brisa 🌱</span>
              <p>{programa.datos?.mensaje_bienvenida || "¡Hola! Soy Brisa 🌱, la asistente de reciclaje de tu conjunto. ¿En qué te ayudo hoy?"}</p></div>
          </div>
          {programa.datos && (
            <ul className="previa-datos">
              <li><Icono nombre="reloj" />{programa.datos.horario_atencion || "Sin horario"}</li>
              <li><Icono nombre="calendario" />{programa.datos.dias_recoleccion || "Sin días definidos"}</li>
              {programa.datos.telefono_contacto && <li><Icono nombre="campana" />{programa.datos.telefono_contacto}</li>}
              {programa.datos.correo_contacto && <li><Icono nombre="hoja" />{programa.datos.correo_contacto}</li>}
            </ul>
          )}
          <Estado tipo="vacio">Los cambios se guardan como evento en Actividad.</Estado>
        </section>
      </div>
    </div>
  );
}
