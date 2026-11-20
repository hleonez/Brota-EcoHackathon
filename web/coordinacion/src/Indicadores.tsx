import { useState } from "react";
import { Espera, fechaBogota, numero, useDatos } from "./portal";
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
  return (
    <section>
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
      {catalogo.error && (
        <Espera error={catalogo.error} reintentar={catalogo.recargar} />
      )}
      {!valido ? (
        <p role="alert">
          Elige una fecha final igual o posterior a la inicial.
        </p>
      ) : !r.datos ? (
        <Espera error={r.error} reintentar={r.recargar} />
      ) : (
        <>
          <div className="row g-3">
            {[
              [numero(r.datos.kg_aceptados) + " kg", "Material aceptado"],
              [numero(r.datos.hogares_participantes), "Hogares participantes"],
              [
                r.datos.valor_estimado === null
                  ? "Sin precio"
                  : "$ " + numero(r.datos.valor_estimado),
                "Valor estimado en COP",
              ],
            ].map(([n, t]) => (
              <div className="col-12 col-md-4" key={t}>
                <div className="eco-tarjeta">
                  <small>{t}</small>
                  <strong className="cifra">{n}</strong>
                </div>
              </div>
            ))}
          </div>
          <section className="eco-tarjeta">
            <h2>Órdenes creadas en el periodo</h2>
            {Object.entries(r.datos.ordenes_por_estado).map(([k, n]) => (
              <div className="medida" key={k}>
                <span>{estados[k] || k}</span>
                <progress
                  aria-label={estados[k] || k}
                  value={n}
                  max={Math.max(
                    1,
                    ...Object.values(r.datos!.ordenes_por_estado),
                  )}
                />
                <b>{numero(n)}</b>
              </div>
            ))}
          </section>
          <section className="eco-tarjeta">
            <h2>Material por método de medición</h2>
            {r.datos.materiales.length ? (
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
                    {r.datos.materiales.map((m) => (
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
              <p>Sin pesajes confirmados en este periodo.</p>
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
