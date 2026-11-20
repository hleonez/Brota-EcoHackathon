import { useState } from "react";
import { Espera, Estado, fechaBogota, numero, useDatos } from "./portal";
import type { Catalogo } from "./tipos";
import { Icono } from "./Iconos";

interface Resumen {
  hogares_participantes: number;
  kg_aceptados: string;
  kg_rechazados: string;
  valor_estimado: string | null;
  ordenes_por_estado: Record<string, number>;
  materiales: {
    material_id: string;
    nombre: string;
    kg_aceptados: string;
    kg_rechazados: string;
    kg_estimados: string;
    kg_bascula: string;
  }[];
}
type Agrupacion = "dia" | "semana" | "mes";
interface Serie {
  serie: { inicio_local: string; kg_aceptados: string; kg_rechazados: string }[];
}
const titulosSerie: Record<Agrupacion, string> = {
  dia: "Kilos aceptados por día",
  semana: "Kilos aceptados por semana",
  mes: "Kilos aceptados por mes",
};
const formatoSerie: Record<Agrupacion, Intl.DateTimeFormatOptions> = {
  dia: { day: "numeric", month: "short" },
  semana: { day: "numeric", month: "short" },
  mes: { month: "short", year: "2-digit" },
};

/** Single-series bar chart of confirmed weighings. Buckets come from GET /v1/reportes/serie. */
function SerieKilos({ agrupacion, datos, error, reintentar }: {
  agrupacion: Agrupacion;
  datos?: Serie;
  error?: string;
  reintentar: () => void;
}) {
  const titulo = titulosSerie[agrupacion];
  if (!datos) return <section className="eco-tarjeta"><h2>{titulo}</h2><Espera error={error} reintentar={reintentar} /></section>;
  const puntos = datos.serie.map((p) => ({
    etiqueta: (agrupacion === "semana" ? "Sem. " : "") + new Intl.DateTimeFormat("es-CO", {
      ...formatoSerie[agrupacion], timeZone: "UTC",
    }).format(new Date(p.inicio_local + "T00:00:00Z")),
    kg: Number(p.kg_aceptados),
  }));
  const maximo = Math.max(...puntos.map((p) => p.kg), 0);
  return (
    <section className="eco-tarjeta">
      <h2>{titulo}</h2>
      {puntos.length === 0 || maximo === 0 ? (
        <Estado tipo="vacio">Sin pesajes confirmados en este periodo.</Estado>
      ) : (
        <figure className="serie">
          <ol className="serie-barras">
            {puntos.map((p) => (
              <li className="serie-barra" key={p.etiqueta} title={p.etiqueta + ": " + numero(p.kg) + " kg"}>
                <span className="serie-valor">{numero(p.kg)} kg</span>
                <span className="serie-relleno" style={{ ["--proporcion" as string]: p.kg / maximo }} aria-hidden="true" />
                <span className="sr-only">{p.etiqueta}</span>
              </li>
            ))}
          </ol>
          <ol className="serie-etiquetas" aria-hidden="true">
            {puntos.map((p) => <li key={p.etiqueta}>{p.etiqueta}</li>)}
          </ol>
          <figcaption>Solo pesajes confirmados. Los periodos sin pesajes no aparecen.</figcaption>
        </figure>
      )}
    </section>
  );
}

const estados: Record<string, string> = {
  nueva: "Recibidas",
  asignada: "Asignadas",
  programada: "Programadas",
  recogida: "Recolectadas",
  rechazada: "No recogidas",
  cancelada: "Canceladas",
};
export default function Indicadores({ gremioId }: { gremioId?: string }) {
  const catalogo = useDatos<Catalogo>(gremioId ? "" : "/v1/catalogos");
  const [flujo, setFlujo] = useState("");
  const [inicio, setInicio] = useState(
    fechaBogota(new Date(Date.now() - 6 * 86400000)),
  );
  const [fin, setFin] = useState(fechaBogota(new Date()));
  const valido = inicio && fin && inicio <= fin;
  const params = new URLSearchParams();
  if (valido) {
    params.set("desde", inicio + "T00:00:00-05:00");
    params.set(
      "hasta",
      new Date(Date.parse(fin + "T00:00:00-05:00") + 86400000).toISOString(),
    );
  }
  if (gremioId || flujo) params.set("gremio_id", gremioId || flujo);
  const r = useDatos<Resumen>(valido ? "/v1/reportes/resumen?" + params : "");
  const dias = valido ? (Date.parse(fin) - Date.parse(inicio)) / 86400000 + 1 : 0;
  const agrupacion: Agrupacion = dias <= 14 ? "dia" : dias <= 92 ? "semana" : "mes";
  const serie = useDatos<Serie>(valido ? "/v1/reportes/serie?" + params + "&agrupacion=" + agrupacion : "");
  const resumen = r.datos;
  const porEstado = resumen ? Object.entries({ ...Object.fromEntries(
    Object.keys(estados).map((estado) => [estado, 0]),
  ), ...resumen.ordenes_por_estado }) : [];
  const escala = Math.max(1, ...porEstado.map(([, cantidad]) => cantidad));
  const sinRegistros = resumen && porEstado.every(([, cantidad]) => cantidad === 0) &&
    resumen.materiales.length === 0 && resumen.hogares_participantes === 0 &&
    Number(resumen.kg_aceptados) === 0 && Number(resumen.kg_rechazados) === 0 &&
    resumen.valor_estimado === null;
  return (
    <section className="impacto" aria-label="Resumen del periodo">
      <fieldset className="eco-tarjeta filtros-impacto">
        <legend>Filtrar periodo</legend>
        <div className="campos">
        <label>
          Desde
          <input
            type="date"
            required
            value={inicio}
            onChange={(e) => setInicio(e.target.value)}
          />
        </label>
        <label>
          Hasta
          <input
            type="date"
            required
            value={fin}
            onChange={(e) => setFin(e.target.value)}
          />
        </label>
        {!gremioId && (
          <label>
            Colectivo
            <select value={flujo} onChange={(e) => setFlujo(e.target.value)}>
              <option value="">Todos los colectivos</option>
              {catalogo.datos?.gremios.map((g) => (
                <option key={g.id} value={g.id}>
                  {g.nombre}
                </option>
              ))}
            </select>
          </label>
        )}
        <button className="btn" onClick={() => { r.recargar(); serie.recargar(); }}>
          Actualizar
        </button>
        </div>
      </fieldset>
      {catalogo.error && (
        <Espera error={catalogo.error} reintentar={catalogo.recargar} />
      )}
      {!valido ? (
        <Estado tipo="error">
          Elige una fecha final igual o posterior a la inicial.
        </Estado>
      ) : !resumen ? (
        <Espera error={r.error} reintentar={r.recargar} />
      ) : sinRegistros ? (
        <Estado tipo="vacio">No hay registros para el periodo y colectivo seleccionados.</Estado>
      ) : (
        <>
          <div className="resumen-impacto">
            {[
              [numero(resumen.kg_aceptados) + " kg", "Material aceptado", "reciclar", "verde"],
              [numero(resumen.hogares_participantes), "Hogares participantes", "casa", "turquesa"],
              [
                resumen.valor_estimado === null
                  ? "Sin precio"
                  : "$ " + numero(resumen.valor_estimado),
                "Valor estimado en COP",
                "puntos",
                "amarillo",
              ],
            ].map(([n, t, icono, tono]) => (
              <div className={"eco-tarjeta impacto-cifra tono-" + tono} key={t}>
                <span className="impacto-icono"><Icono nombre={icono} /></span>
                <span className="impacto-texto">{t}</span>
                <strong className="cifra">{n}</strong>
              </div>
            ))}
          </div>
          <SerieKilos agrupacion={agrupacion} datos={serie.datos} error={serie.error} reintentar={serie.recargar} />
          <section className="eco-tarjeta">
            <h2>Órdenes creadas en el periodo</h2>
            {porEstado.map(([k, n]) => (
              <div className="medida" key={k}>
                <span>{estados[k] || k}</span>
                <b>{numero(n)}</b>
                <progress aria-label={estados[k] || k} value={n} max={escala} />
              </div>
            ))}
          </section>
          <section className="eco-tarjeta">
            <h2>Material por método de medición</h2>
            {resumen.materiales.length ? (
              <div className="desliza">
                <table>
                  <thead>
                    <tr>
                      {[
                        "Material",
                        "Aceptado (kg)",
                        "Rechazado (kg)",
                        "Báscula (kg)",
                        "Estimado por baldes (kg)",
                      ].map((t) => (
                        <th key={t}>{t}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {resumen.materiales.map((m) => (
                      <tr key={m.material_id}>
                        <th>{m.nombre}</th>
                        {[
                          m.kg_aceptados,
                          m.kg_rechazados,
                          m.kg_bascula,
                          m.kg_estimados,
                        ].map((v, i) => (
                          <td key={i}>{numero(v)}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <Estado tipo="vacio">Sin pesajes confirmados en este periodo.</Estado>
            )}
            <p className="tenue">
              El valor estimado usa los precios aplicados a los pesajes
              confirmados.
            </p>
          </section>
        </>
      )}
    </section>
  );
}
