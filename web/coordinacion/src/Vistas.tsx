import { useState } from "react";
import type { Accion } from "./Panel";
import type { ItemCatalogo, Orden, Recolector } from "./tipos";
import { diaDe, hace, textoFranja } from "./util";

interface Comunes {
  servicios: Map<string, ItemCatalogo>;
  recientes: Set<string>;
  onAccion: (a: Accion) => void;
}

function porFranja(a: Orden, b: Orden): number {
  const x = a.asignacion?.inicio ?? "9999";
  const y = b.asignacion?.inicio ?? "9999";
  return x < y ? -1 : x > y ? 1 : a.created_at < b.created_at ? -1 : 1;
}

// ------------------------------------------------------------------ tarjeta

function Tarjeta({ orden: o, servicios, recientes, onAccion, sinRecolector }: Comunes & { orden: Orden; sinRecolector?: boolean }) {
  const a = o.asignacion;
  return (
    <article className={`tarjeta estado-${o.estado} ${o.estado === "nueva" && recientes.has(o.id) ? "reciente" : ""}`}>
      <div className="tarjeta-cabeza">
        <span className="codigo">{o.codigo_pasaporte}</span>
        <span className="tenue">{hace(o.created_at)}</span>
      </div>
      <div className="ubicacion">📍 {o.ubicacion_operativa}</div>
      <div className="fila-datos">
        <span>👤 {o.contacto_nombre ?? "Sin nombre"}</span>
        {o.tipo_servicio_ids.map((id) => {
          const s = servicios.get(id);
          return s ? <span key={id} className="chip">{s.nombre}</span> : null;
        })}
      </div>
      {o.observacion && <div className="nota">📝 {o.observacion}</div>}
      {a && o.estado === "asignada" && (
        <div className="asignacion">
          {!sinRecolector && <strong>🚲 {a.recolector_nombre}</strong>} <span>🕑 {textoFranja(a.inicio, a.fin)}</span>
          <span className="tenue"> · aviso por {a.forma_aviso}</span>
          {o.reasignaciones > 0 && <span className="tenue"> · reasignada {o.reasignaciones}×</span>}
        </div>
      )}
      <div className="acciones">
        {o.estado === "nueva" && (
          <button className="btn primario grande" onClick={() => onAccion({ tipo: "asignar", orden: o })}>
            🚲 Asignar recolector
          </button>
        )}
        {o.estado === "asignada" && (
          <>
            <button className="btn exito" onClick={() => onAccion({ tipo: "recogida", orden: o })}>✅ Recogida</button>
            <button className="btn peligro" onClick={() => onAccion({ tipo: "rechazada", orden: o })}>❌ Rechazada</button>
            <button className="btn" onClick={() => onAccion({ tipo: "asignar", orden: o })}>↺ Reasignar</button>
          </>
        )}
      </div>
    </article>
  );
}

// ------------------------------------------------------------------ bandeja

export function VistaBandeja({ nuevas, asignadas, ...c }: Comunes & { nuevas: Orden[]; asignadas: Orden[] }) {
  const porLlegada = [...nuevas].sort((a, b) => (a.created_at < b.created_at ? -1 : 1)); // la más antigua primero
  return (
    <div className="columnas">
      <section>
        <h2>Nuevas <span className="tenue">· por asignar ({nuevas.length})</span></h2>
        {porLlegada.length ? porLlegada.map((o) => <Tarjeta key={o.id} orden={o} {...c} />) : (
          <Vacio texto="No hay solicitudes nuevas. Cuando un vecino pida por WhatsApp, aparece aquí." />
        )}
      </section>
      <section>
        <h2>Asignadas <span className="tenue">· por cerrar ({asignadas.length})</span></h2>
        {asignadas.length ? [...asignadas].sort(porFranja).map((o) => <Tarjeta key={o.id} orden={o} {...c} />) : (
          <Vacio texto="Nada en ruta por ahora." />
        )}
      </section>
    </div>
  );
}

// ------------------------------------------------------------------ rutas

type FiltroDia = "todas" | "hoy" | "manana" | "sin";

export function VistaRutas({ asignadas, recolectores, ...c }: Comunes & { asignadas: Orden[]; recolectores: Recolector[] }) {
  const [filtro, setFiltro] = useState<FiltroDia>("todas");
  const visibles = asignadas.filter((o) => {
    if (filtro === "todas") return true;
    const d = diaDe(o.asignacion?.inicio ?? null);
    return filtro === d;
  });
  // Recolectores del gremio, más cualquiera que tenga paradas y ya no esté activo.
  const lista = [...recolectores];
  for (const o of visibles) {
    const a = o.asignacion!;
    if (!lista.some((r) => r.id === a.recolector_id)) {
      lista.push({ id: a.recolector_id, nombre: a.recolector_nombre, telefono_contacto: null, gremio_id: o.gremio_id, activo: false });
    }
  }
  const conParadas = lista
    .map((r) => ({ r, paradas: visibles.filter((o) => o.asignacion?.recolector_id === r.id).sort(porFranja) }))
    .filter((x) => x.paradas.length);
  const libres = lista.filter((r) => !conParadas.some((x) => x.r.id === r.id));

  return (
    <div>
      <div className="filtros" role="group" aria-label="Día">
        {([["todas", "Todas"], ["hoy", "Hoy"], ["manana", "Mañana"], ["sin", "Sin hora fija"]] as const).map(([k, t]) => (
          <button key={k} className={`chip-filtro ${filtro === k ? "activo" : ""}`} onClick={() => setFiltro(k)}>{t}</button>
        ))}
      </div>
      {conParadas.length === 0 && <Vacio texto="No hay paradas para este filtro. Asigna solicitudes desde la bandeja." />}
      <div className="rutas">
        {conParadas.map(({ r, paradas }) => (
          <section key={r.id} className="ruta">
            <header>
              <h3>🚲 {r.nombre}</h3>
              <span className="tenue">{paradas.length} {paradas.length === 1 ? "parada" : "paradas"}</span>
              {r.telefono_contacto ? (
                <a className="btn" href={`tel:${r.telefono_contacto}`}>📞 {r.telefono_contacto}</a>
              ) : (
                <span className="tenue">sin teléfono</span>
              )}
            </header>
            <ol>
              {paradas.map((o) => (
                <li key={o.id}><Tarjeta orden={o} sinRecolector {...c} /></li>
              ))}
            </ol>
          </section>
        ))}
      </div>
      {libres.length > 0 && <p className="tenue">Sin paradas: {libres.map((r) => r.nombre).join(", ")}.</p>}
      <p className="tenue">El recolector no usa ninguna app: llámalo o déjale el recado con sus paradas.</p>
    </div>
  );
}

// ------------------------------------------------------------------ historial

type FiltroResultado = "todas" | "recogida" | "rechazada";

export function VistaHistorial({ ordenes, servicios }: Comunes & { ordenes: Orden[] }) {
  const [filtro, setFiltro] = useState<FiltroResultado>("todas");
  const cerradas = ordenes
    .filter((o) => o.estado === "recogida" || o.estado === "rechazada")
    .sort((a, b) => ((a.resultado?.ocurrido_at ?? "") < (b.resultado?.ocurrido_at ?? "") ? 1 : -1));
  const hoy = cerradas.filter((o) => diaDe(o.resultado?.ocurrido_at ?? null) === "hoy");
  const visibles = cerradas.filter((o) => filtro === "todas" || o.estado === filtro);
  return (
    <div>
      <div className="resumen">
        <div className="kpi"><span className="kpi-n">{hoy.filter((o) => o.estado === "recogida").length}</span>recogidas hoy</div>
        <div className="kpi"><span className="kpi-n">{hoy.filter((o) => o.estado === "rechazada").length}</span>rechazadas hoy</div>
        <div className="kpi"><span className="kpi-n">{cerradas.length}</span>cerradas en total</div>
      </div>
      <div className="filtros" role="group" aria-label="Resultado">
        {([["todas", "Todas"], ["recogida", "Recogidas"], ["rechazada", "Rechazadas"]] as const).map(([k, t]) => (
          <button key={k} className={`chip-filtro ${filtro === k ? "activo" : ""}`} onClick={() => setFiltro(k)}>{t}</button>
        ))}
      </div>
      {visibles.length === 0 ? <Vacio texto="Aún no hay órdenes cerradas." /> : (
        <ul className="historial">
          {visibles.map((o) => (
            <li key={o.id} className={`estado-${o.estado}`}>
              <span className="codigo">{o.codigo_pasaporte}</span>
              <span>{o.ubicacion_operativa}</span>
              <span className="tenue">👤 {o.contacto_nombre ?? "—"} · {o.tipo_servicio_ids.map((id) => servicios.get(id)?.nombre).filter(Boolean).join(", ")}</span>
              <span>
                {o.estado === "recogida" ? "✅ Recogida" : `❌ ${o.resultado?.motivo_rechazo_nombre ?? "Rechazada"}`}
                {o.asignacion && <span className="tenue"> · 🚲 {o.asignacion.recolector_nombre}</span>}
              </span>
              <span className="tenue">{o.resultado ? hace(o.resultado.ocurrido_at) : ""}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function Vacio({ texto }: { texto: string }) {
  return <p className="vacio">{texto}</p>;
}
