/**
 * Panel de la Fundación: impacto del programa en el barrio Villas de San Pablo y en cada conjunto,
 * con comparación contra el periodo anterior, y los informes descargables (PDF con gráficas,
 * Certificado Verde y Excel). Solo totales: sin nombres, celulares ni apartamentos.
 */
import { useEffect, useMemo, useState, type CSSProperties } from "react";
import { BotonDescarga, CertificadoVerde, LigaTorres, periodoMes, useConteo } from "./AdminExtra";
import { descargarArchivo } from "./api";
import { Icono } from "./Iconos";
import Indicadores from "./Indicadores";
import { MarcoPanel, enlaceCuenta, type CuentaPanel, type GrupoPanel } from "./MarcoPanel";
import { Espera, Estado, useDatos } from "./portal";

const enc = encodeURIComponent;
const BARRIO = "Villas de San Pablo";

interface Resumen {
  kg_aceptados: string; kg_rechazados: string; valor_estimado: string | null; hogares_participantes: number;
  tasa_rechazo_peso: number | null; resultados: { recogidas: number; rechazadas: number };
  ordenes_por_estado: Record<string, number>;
  materiales: { material_id: string; nombre: string; kg_aceptados: string }[];
}
interface Serie { agrupacion: string; serie: { inicio_local: string; kg_aceptados: string }[] }
interface Conjunto { id: string; nombre: string; etapa: string | null }

type Ventana = "mes" | "3m" | "6m" | "anio";
const ventanas: [Ventana, string][] = [["mes", "Este mes"], ["3m", "Últimos 3 meses"], ["6m", "Últimos 6 meses"], ["anio", "Este año"]];
function rango(v: Ventana) {
  const mesActual = Number(new Intl.DateTimeFormat("en-CA", { timeZone: "America/Bogota", month: "numeric" }).format(new Date()));
  const meses = v === "mes" ? 1 : v === "3m" ? 3 : v === "6m" ? 6 : mesActual;
  const actual = periodoMes(0, meses);
  const anterior = periodoMes(-meses, meses);
  return { ...actual, meses, anterior, nombre: ventanas.find(([k]) => k === v)![1].toLowerCase() };
}
function consulta(desde: string, hasta: string, conjunto: string) {
  return `desde=${enc(desde)}&hasta=${enc(hasta)}` + (conjunto ? `&conjunto_id=${conjunto}` : "");
}
const pesos = (n: number) => "$" + Math.round(n).toLocaleString("es-CO");
const kilos = (n: number, d = 0) => n.toLocaleString("es-CO", { maximumFractionDigits: d }) + " kg";
function cambio(actual: number, anterior: number): { texto: string; sube: boolean } | null {
  if (anterior <= 0) return actual > 0 ? { texto: "nuevo", sube: true } : null;
  const c = Math.round(((actual - anterior) / anterior) * 100);
  return { texto: `${c >= 0 ? "+" : ""}${c} %`, sube: c >= 0 };
}
const mesCorto = (iso: string) =>
  new Intl.DateTimeFormat("es-CO", { month: "short", timeZone: "UTC" }).format(new Date(iso + "T12:00:00Z")).replace(".", "");

const grupos: GrupoPanel[] = [
  { enlaces: [{ id: "inicio", texto: "Inicio" }] },
  { titulo: "Impacto", enlaces: [{ id: "impacto", texto: "Por conjunto" }, { id: "informes", texto: "Informes" }, { id: "liga de torres", texto: "Liga de torres" }] },
];
const titulos: Record<string, string> = { inicio: "Impacto del programa", impacto: "Impacto por conjunto", informes: "Informes", "liga de torres": "Liga de torres" };

export function PanelFundacion({ cuenta }: { cuenta: CuentaPanel }) {
  const [activo, navegar] = useState("inicio");
  const [ventana, setVentana] = useState<Ventana>("3m");
  const [conjunto, setConjunto] = useState("");
  const conjuntos = useDatos<Conjunto[]>("/v1/conjuntos");
  const nombreTerritorio = conjunto ? conjuntos.datos?.find((c) => c.id === conjunto)?.nombre ?? "Conjunto" : `Barrio ${BARRIO}`;
  const r = useMemo(() => rango(ventana), [ventana]);
  const filtros = activo !== enlaceCuenta.id && activo !== "liga de torres" && (
    <div className="fundacion-filtros">
      <label className="filtro-select con-icono"><Icono nombre="ubicacion" /><span className="visually-hidden">Territorio</span>
        <select value={conjunto} onChange={(e) => setConjunto(e.target.value)}>
          <option value="">Todo el barrio</option>
          {(conjuntos.datos ?? []).map((c) => <option key={c.id} value={c.id}>{c.nombre}</option>)}
        </select>
      </label>
      <label className="filtro-select con-icono"><Icono nombre="calendario" /><span className="visually-hidden">Periodo</span>
        <select value={ventana} onChange={(e) => setVentana(e.target.value as Ventana)}>
          {ventanas.map(([k, t]) => <option key={k} value={k}>{t}</option>)}
        </select>
      </label>
    </div>
  );
  return (
    <MarcoPanel grupos={grupos} activo={activo} navegar={navegar} cuenta={cuenta} contexto="Fundación Santo Domingo"
      titulo={activo === enlaceCuenta.id ? enlaceCuenta.texto : titulos[activo]} portada={activo === "inicio"} acciones={filtros}>
      {activo === "inicio" ? <Inicio r={r} conjunto={conjunto} territorio={nombreTerritorio} navegar={navegar} />
        : activo === "impacto" ? <PorConjunto r={r} conjuntos={conjuntos.datos} elegido={conjunto} elegir={setConjunto} />
        : activo === "informes" ? <Informes r={r} conjunto={conjunto} territorio={nombreTerritorio} />
        : <LigaTorres conjuntoId={conjunto || undefined} />}
    </MarcoPanel>
  );
}

// ------------------------------------------------------------------ inicio (diseño «Impacto del programa»)

function KpiImpacto({ imagen, titulo, valor, formato, variacion, tono }: {
  imagen: string; titulo: string; valor: number; formato: (n: number) => string;
  variacion: ReturnType<typeof cambio>; tono: string;
}) {
  const v = useConteo(valor);
  return (
    <article className={"impacto-kpi tono-" + tono}>
      <img src={imagen} alt="" />
      <div>
        <h3>{titulo}</h3>
        <strong>{formato(v)}</strong>
        {variacion && (
          <span className={"impacto-cambio" + (variacion.sube ? "" : " baja")} title="Comparado con el periodo anterior de igual duración">
            <Icono nombre={variacion.sube ? "flecha" : "abajo"} />{variacion.texto}
          </span>
        )}
      </div>
    </article>
  );
}

function Inicio({ r, conjunto, territorio, navegar }: {
  r: ReturnType<typeof rango>; conjunto: string; territorio: string; navegar: (id: string) => void;
}) {
  const actual = useDatos<Resumen>(`/v1/reportes/resumen?${consulta(r.desde, r.hasta, conjunto)}`);
  const anterior = useDatos<Resumen>(`/v1/reportes/resumen?${consulta(r.anterior.desde, r.anterior.hasta, conjunto)}`);
  const agrupacion = r.meses === 1 ? "semana" : "mes";
  const serie = useDatos<Serie>(`/v1/reportes/serie?agrupacion=${agrupacion}&${consulta(r.desde, r.hasta, conjunto)}`);
  const a = actual.datos, b = anterior.datos;
  const puntos = serie.datos?.serie ?? [];
  const valores = puntos.map((p) => Number(p.kg_aceptados));
  const tope = Math.max(1, ...valores) * 1.15;
  const crecimiento = valores.length > 1 ? cambio(valores[valores.length - 1], valores[0]) : null;
  return (
    <>
      <header className="impacto-cabeza">
        <span className="portada-chispas" aria-hidden="true" />
        <h2>Impacto del programa</h2>
        <p>Fundación Santo Domingo · {territorio} · {r.nombre}</p>
      </header>
      {!a ? <Espera error={actual.error} reintentar={actual.recargar} /> : (
        <div className="impacto-kpis">
          <KpiImpacto imagen="/panel/kpi-reciclaje.webp" titulo="Kilos aprovechados" tono="verde"
            valor={Number(a.kg_aceptados)} formato={(n) => kilos(n)} variacion={b ? cambio(Number(a.kg_aceptados), Number(b.kg_aceptados)) : null} />
          <KpiImpacto imagen="/panel/kpi-casa.webp" titulo="Hogares participantes" tono="lila"
            valor={a.hogares_participantes} formato={(n) => Math.round(n).toLocaleString("es-CO")}
            variacion={b ? cambio(a.hogares_participantes, b.hogares_participantes) : null} />
          <KpiImpacto imagen="/panel/kpi-monedas.webp" titulo="Ingresos estimados de recicladores" tono="amarillo"
            valor={Number(a.valor_estimado ?? 0)} formato={pesos}
            variacion={b ? cambio(Number(a.valor_estimado ?? 0), Number(b.valor_estimado ?? 0)) : null} />
        </div>
      )}
      <div className="impacto-fila">
        <section className="eco-tarjeta impacto-grafica" aria-labelledby="grafica-titulo">
          <div className="impacto-grafica-cabeza">
            <h3 id="grafica-titulo"><img src="/panel/brote.webp" alt="" />Kilos aprovechados por {agrupacion}</h3>
            {crecimiento && <span className={"impacto-insignia" + (crecimiento.sube ? "" : " baja")}><strong>{crecimiento.texto}</strong>vs. {mesCorto(puntos[0].inicio_local)}</span>}
          </div>
          {!serie.datos ? <Espera error={serie.error} reintentar={serie.recargar} /> : puntos.length === 0 ? (
            <div className="vacio-clay"><p>Sin pesajes confirmados en {r.nombre}.</p></div>
          ) : (
            <div className="barras" role="img" aria-label={puntos.map((p) => `${mesCorto(p.inicio_local)}: ${kilos(Number(p.kg_aceptados))}`).join(", ")}>
              <div className="barras-eje" aria-hidden="true">
                {[4, 3, 2, 1, 0].map((i) => <span key={i}>{kilos((tope / 4) * i)}</span>)}
              </div>
              <div className="barras-zona">
                {puntos.map((p, i) => (
                  <div key={p.inicio_local} className="barras-columna" style={{ "--alto": `${(Number(p.kg_aceptados) / tope) * 100}%`, "--n": i } as CSSProperties}>
                    <span className="barras-valor">{kilos(Number(p.kg_aceptados))}</span>
                    <span className="barras-barra" />
                    <span className="barras-etiqueta">{agrupacion === "mes" ? mesCorto(p.inicio_local) : p.inicio_local.slice(8, 10) + " " + mesCorto(p.inicio_local)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </section>
        <div className="impacto-escena">
          <img src="/panel/recicladores.webp" alt="" />
          <button type="button" className="impacto-boton" onClick={() => navegar("informes")}>
            <Icono nombre="informes" />Ver informes<Icono nombre="flecha" />
          </button>
        </div>
      </div>
      {a && (
        <ul className="impacto-secundarios">
          <li><Icono nombre="check" /><strong>{a.resultados.recogidas}</strong>recolecciones hechas</li>
          <li><Icono nombre="bandeja" /><strong>{Object.values(a.ordenes_por_estado).reduce((s, n) => s + n, 0)}</strong>solicitudes por WhatsApp</li>
          <li><Icono nombre="motivos" /><strong>{a.tasa_rechazo_peso === null ? "—" : `${(a.tasa_rechazo_peso * 100).toLocaleString("es-CO", { maximumFractionDigits: 1 })} %`}</strong>de rechazo por peso</li>
          <li><Icono nombre="materiales" /><strong>{a.materiales.length}</strong>materiales distintos</li>
        </ul>
      )}
    </>
  );
}

// ------------------------------------------------------------------ comparación por conjunto

function FilaConjunto({ c, r, maximo, informar, elegido, elegir }: {
  c: Conjunto; r: ReturnType<typeof rango>; maximo: number; informar: (id: string, kg: number) => void;
  elegido: boolean; elegir: () => void;
}) {
  const d = useDatos<Resumen>(`/v1/reportes/resumen?${consulta(r.desde, r.hasta, c.id)}`);
  const kg = d.datos ? Number(d.datos.kg_aceptados) : 0;
  useEffect(() => {
    if (d.datos) informar(c.id, kg);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [d.datos]);
  return (
    <li className={"conjunto-fila" + (elegido ? " elegido" : "")}>
      <span className="registro-avatar tono-turquesa" aria-hidden="true"><Icono nombre="unidades" /></span>
      <div className="conjunto-texto">
        <strong>{c.nombre}</strong>
        <small>{c.etapa ?? `Barrio ${BARRIO}`}</small>
        <span className="progreso" aria-hidden="true">
          <span className="progreso-barra" style={{ "--ancho": `${maximo ? (kg / maximo) * 100 : 0}%` } as CSSProperties} />
        </span>
      </div>
      {!d.datos ? <Espera error={d.error} reintentar={d.recargar} /> : (
        <dl className="conjunto-cifras">
          <div><dt>Kilos</dt><dd>{kilos(kg, 1)}</dd></div>
          <div><dt>Hogares</dt><dd>{d.datos.hogares_participantes}</dd></div>
          <div><dt>Recolecciones</dt><dd>{d.datos.resultados.recogidas}</dd></div>
          <div><dt>Rechazo</dt><dd>{d.datos.tasa_rechazo_peso === null ? "—" : `${(d.datos.tasa_rechazo_peso * 100).toFixed(1)} %`}</dd></div>
        </dl>
      )}
      <button type="button" className="btn btn-sm" onClick={elegir} aria-pressed={elegido}>{elegido ? "Viendo" : "Ver solo este"}</button>
    </li>
  );
}

function PorConjunto({ r, conjuntos, elegido, elegir }: {
  r: ReturnType<typeof rango>; conjuntos?: Conjunto[]; elegido: string; elegir: (id: string) => void;
}) {
  const barrio = useDatos<Resumen>(`/v1/reportes/resumen?${consulta(r.desde, r.hasta, "")}`);
  const [kgPor, setKgPor] = useState<Record<string, number>>({});
  const maximo = Math.max(0, ...Object.values(kgPor));
  return (
    <>
      <section className="eco-tarjeta">
        <div className="lista-encabezado">
          <h2>Barrio {BARRIO} · {r.nombre}</h2>
          {elegido && <button type="button" className="btn" onClick={() => elegir("")}>Ver todo el barrio</button>}
        </div>
        {barrio.datos && (
          <p className="conjunto-total">
            <strong>{kilos(Number(barrio.datos.kg_aceptados), 1)}</strong> aprovechados en el barrio ·
            <strong> {barrio.datos.hogares_participantes}</strong> hogares participantes ·
            <strong> {barrio.datos.resultados.recogidas}</strong> recolecciones
          </p>
        )}
        {!conjuntos ? <Estado tipo="carga">Cargando conjuntos…</Estado> : (
          <ul className="conjuntos-lista">
            {conjuntos.map((c) => (
              <FilaConjunto key={c.id} c={c} r={r} maximo={maximo} elegido={elegido === c.id} elegir={() => elegir(c.id)}
                informar={(id, kg) => setKgPor((m) => (m[id] === kg ? m : { ...m, [id]: kg }))} />
            ))}
          </ul>
        )}
        <p className="nota-privacidad"><Icono nombre="piloto" />Los kilos de un conjunto cuentan solo los pesajes con torre de origen comprobada; los que no la tienen suman al barrio.</p>
      </section>
      <Indicadores />
    </>
  );
}

// ------------------------------------------------------------------ informes

function Informes({ r, conjunto, territorio }: { r: ReturnType<typeof rango>; conjunto: string; territorio: string }) {
  const [error, setError] = useState<string | null>(null);
  async function bajar(ruta: string, nombre: string) {
    setError(null);
    try { await descargarArchivo(ruta, nombre); } catch (e) { setError((e as Error).message); }
  }
  const q = consulta(r.desde, r.hasta, conjunto);
  return (
    <>
      <div className="informes">
        <article className="eco-tarjeta informe tono-verde">
          <img src="/panel/kpi-reciclaje.webp" alt="" />
          <div>
            <h2>Informe de impacto</h2>
            <p>PDF con indicadores, gráficas de kilos por {r.meses === 1 ? "semana" : "mes"} y por material, comparación entre conjuntos y contra el periodo anterior.</p>
            <small>{territorio} · {r.nombre}</small>
          </div>
          <BotonDescarga onClick={() => bajar(`/v1/reportes/informe-impacto?${q}`, "informe-impacto.pdf")}>Descargar PDF</BotonDescarga>
        </article>
        <article className="eco-tarjeta informe tono-turquesa">
          <img src="/panel/kpi-casa.webp" alt="" />
          <div>
            <h2>Datos del periodo en Excel</h2>
            <p>Resumen, materiales, torres y órdenes del periodo, sin datos de contacto, para análisis propios.</p>
            <small>{territorio} · {r.nombre}</small>
          </div>
          <BotonDescarga onClick={() => bajar(`/v1/reportes/exportacion?${q}`, "brota-periodo.xlsx")}>Descargar Excel</BotonDescarga>
        </article>
      </div>
      {error && <Estado tipo="error">{error}</Estado>}
      <CertificadoVerde conjuntoId={conjunto || undefined} />
    </>
  );
}
