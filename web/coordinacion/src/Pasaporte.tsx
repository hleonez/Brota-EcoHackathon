import { useState } from "react";
import { Espera, useDatos } from "./portal";
import type { Orden } from "./tipos";
export default function Pasaporte({ orden }: { orden: Orden }) {
  const [abierto, setAbierto] = useState(false);
  const r = useDatos<{
    eventos: { tipo: string; ocurrido_at: string; orden_id: string | null }[];
  }>(abierto ? "/v1/solicitudes/" + orden.solicitud_id + "/pasaporte" : "");
  return (
    <div>
      <button
        className="btn"
        aria-expanded={abierto}
        onClick={() => setAbierto(!abierto)}
      >
        Pasaporte {orden.codigo_pasaporte}
      </button>
      {abierto &&
        (!r.datos ? (
          <Espera error={r.error} reintentar={r.recargar} />
        ) : (
          <ol>
            {r.datos.eventos
              .filter((e) => !e.orden_id || e.orden_id === orden.id)
              .map((e, i) => (
                <li key={i}>
                  {e.tipo.replaceAll("_", " ")} ·{" "}
                  {new Date(e.ocurrido_at).toLocaleString("es-CO", {
                    timeZone: "America/Bogota",
                  })}
                </li>
              ))}
          </ol>
        ))}
    </div>
  );
}
