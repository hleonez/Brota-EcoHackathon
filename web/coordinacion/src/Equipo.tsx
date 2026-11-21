import { useState } from "react";
import { pedir } from "./api";
import { BotonBaja, Campo, Formulario } from "./Formulario";
import { Estado, useDatos } from "./portal";
import type { Orden, Recolector } from "./tipos";
import { claveNueva } from "./util";

type Huerta = { id: string; nombre: string; gremio_id: string; activo: boolean };

/** Coordination team: list, add and remove members of the collective.
 *  Removing deactivates the member; their assignments and weighings keep their history. */
export function EquipoColectivo({ gremioId, organico, recolectores, abiertas, recargar }: {
  gremioId: string;
  organico: boolean;
  recolectores: Recolector[];
  abiertas: Orden[];
  recargar: () => void;
}) {
  const [aviso, setAviso] = useState<{ tipo: "exito" | "error"; texto: string } | null>(null);
  const huertas = useDatos<Huerta[]>(organico ? "/v1/huertas" : "");
  const huertasDelGremio = huertas.datos?.filter((h) => h.activo && h.gremio_id === gremioId) ?? [];
  const tipo = organico ? "huerteros" : "recicladores";

  async function eliminar(r: Recolector) {
    setAviso(null);
    try {
      await pedir("PATCH", `/v1/${r.tipo === "huertero" ? "huerteros" : "recicladores"}/${r.id}`, {
        cuerpo: { version_esperada: r.version, activo: false },
        clave: claveNueva(),
      });
      setAviso({ tipo: "exito", texto: `${r.nombre} salió del equipo. Su historial se conserva.` });
      recargar();
    } catch (e) {
      setAviso({ tipo: "error", texto: (e as Error).message });
    }
  }

  return (
    <div className="row g-3">
      <div className="col-12 col-lg-7">
        <section className="eco-tarjeta">
          <h2>Integrantes del colectivo</h2>
          {aviso && <Estado tipo={aviso.tipo}>{aviso.texto}</Estado>}
          {recolectores.length ? (
            <ul className="lista-equipo">
              {recolectores.map((r) => {
                const asignaciones = abiertas.filter((o) => o.asignacion?.recolector_id === r.id).length;
                return (
                  <li key={r.id}>
                    <div>
                      <strong>{r.nombre}</strong>
                      <span>{asignaciones} {asignaciones === 1 ? "asignación vigente" : "asignaciones vigentes"}</span>
                    </div>
                    <div className="registro-acciones">
                      {r.telefono_contacto && (
                        <a className="btn btn-sm" href={`tel:${r.telefono_contacto}`} aria-label={`Llamar a ${r.nombre}`}>Llamar</a>
                      )}
                      <BotonBaja texto="Eliminar" alConfirmar={() => eliminar(r)} />
                    </div>
                  </li>
                );
              })}
            </ul>
          ) : <Estado tipo="vacio">Aún no hay integrantes activos.</Estado>}
        </section>
      </div>
      <div className="col-12 col-lg-5">
        <Formulario
          titulo="Agregar integrante"
          accion="Agregar"
          preparar={(v) => ({
            ruta: tipo,
            cuerpo: {
              gremio_id: gremioId,
              nombre: v.nombre,
              telefono_contacto: v.telefono_contacto || null,
              ...(organico ? { huerta_id: v.huerta_id } : {}),
            },
          })}
          alGuardar={() => { setAviso(null); recargar(); }}
        >
          <Campo nombre="nombre" titulo="Nombre" maxLength={120} />
          <Campo nombre="telefono_contacto" titulo="Teléfono de contacto (opcional)" tipo="tel" opcional />
          {organico && (
            huertas.error
              ? <Estado tipo="error">{huertas.error}</Estado>
              : <Campo key={huertasDelGremio.length} nombre="huerta_id" titulo="Huerta"
                  opciones={huertasDelGremio.map((h) => [h.id, h.nombre])} />
          )}
        </Formulario>
      </div>
    </div>
  );
}
