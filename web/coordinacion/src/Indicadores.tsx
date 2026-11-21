import { useState } from "react";
import { Espera, Estado, fechaBogota, numero, useDatos } from "./portal";
import type { Catalogo } from "./tipos";

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
        <button className="btn" onClick={r.recargar}>
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
              [numero(resumen.kg_aceptados) + " kg", "Material aceptado"],
              [numero(resumen.hogares_participantes), "Hogares participantes"],
              [
                resumen.valor_estimado === null
                  ? "Sin precio"
                  : "$ " + numero(resumen.valor_estimado),
                "Valor estimado en COP",
              ],
            ].map(([n, t]) => (
              <div className="eco-tarjeta impacto-cifra" key={t}>
                <span>{t}</span>
                <strong className="cifra">{n}</strong>
              </div>
            ))}
          </div>
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
