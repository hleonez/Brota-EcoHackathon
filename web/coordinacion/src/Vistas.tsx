import { useState, type FormEvent } from "react";
import { api, ErrorApi } from "./api";
import { Espera, useDatos } from "./portal";
import Pasaporte from "./Pasaporte";
import { Avisos } from "./Operacion";
import type { Accion } from "./Panel";
import type { Caso, ItemCatalogo, Orden, Recolector } from "./tipos";
import { claveParaEnvio, diaDe, hace, textoFranja } from "./util";

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

function Tarjeta({ orden: o, servicios, recientes, onAccion, sinRecolector, detalle }: Comunes & { orden: Orden; sinRecolector?: boolean; detalle?: boolean }) {
  const a = o.asignacion;
  return (
    <article className={`tarjeta estado-${o.estado} ${o.estado === "nueva" && recientes.has(o.id) ? "reciente" : ""}`}>
      <div className="tarjeta-cabeza">
        <span className="codigo">{o.codigo_pasaporte}</span><b>{o.estado==="nueva"?"Recibida":o.estado === "asignada" ? (a?.inicio && a.fin ? "Programada" : "Asignada") : o.estado}</b>
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
      {o.residuos?.length > 0 && (
        <ul className="residuos" aria-label="Materiales declarados">
          {o.residuos.map((r) => (
            <li key={r.residuo_id} className={r.estado === "revision" ? "revisar" : ""}>
              <span className="residuo-nombre">
                {r.emoji} {r.nombre}
                {r.cantidad && <span className="tenue"> · {r.cantidad}</span>}
                {r.estado === "revision" ? <span className="marca-revisar">🔎 revisar al recoger</span> : <span className="marca-ok">✔</span>}
              </span>
              {r.chequeos.length > 0 && <span className="tenue chequeos">{r.chequeos.join(" · ")}</span>}
            </li>
          ))}
        </ul>
      )}
      {o.observacion && <div className="nota">📝 {o.observacion}</div>}
      {a && o.estado === "asignada" && (
        <div className="asignacion">
          {!sinRecolector && <strong>🚲 {a.recolector_nombre}</strong>} <span>🕑 {textoFranja(a.inicio, a.fin)}</span>
          <span className="tenue"> · aviso por {a.forma_aviso}</span>
          {o.reasignaciones > 0 && <span className="tenue"> · reasignada {o.reasignaciones}×</span>}
        </div>
      )}
      {detalle && <><Pasaporte orden={o} /><Avisos id={o.id} /></>}
      <div className="acciones">
        {!detalle && <button className="btn" onClick={() => onAccion({ tipo: "detalle", orden: o })}>Ver detalle</button>}
        {detalle && (o.estado === "asignada" || o.estado === "nueva") && (
          <button className="btn" onClick={() => onAccion({ tipo: "cancelar", orden: o })}>Cancelar recolección</button>
        )}
        {o.estado === "nueva" && (
          <button className="btn primario grande" onClick={() => onAccion({ tipo: "asignar", orden: o })}>
            🚲 Asignar recolector
          </button>
        )}
        {o.estado === "asignada" && (
          <>
            <button disabled={!a?.inicio || !a.fin} className="btn exito" onClick={() => onAccion({ tipo: "recogida", orden: o })}>✅ Recogida</button>
            <button disabled={!a?.inicio || !a.fin} className="btn peligro" onClick={() => onAccion({ tipo: "rechazada", orden: o })}>❌ Rechazada</button>
            <button className="btn" onClick={() => onAccion({ tipo: "programar", orden: o })}>Programar</button>
            <button className="btn" onClick={() => onAccion({ tipo: "reasignar", orden: o })}>Reasignar</button>
          </>
        )}
      </div>
    </article>
  );
}

export function DetalleSolicitud({ id, ...comunes }: Comunes & { id: string }) {
  const consulta = useDatos<Orden>("/v1/ordenes/" + encodeURIComponent(id));
  return consulta.datos
    ? <Tarjeta orden={consulta.datos} {...comunes} detalle />
    : <Espera error={consulta.error} reintentar={consulta.recargar} />;
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

type FiltroResultado = "todas" | "recogida" | "rechazada" | "cancelada";

export function VistaHistorial({ ordenes, servicios, onAccion }: Comunes & { ordenes: Orden[] }) {
  const [filtro, setFiltro] = useState<FiltroResultado>("todas");
  const cerradas = ordenes
    .filter((o) => o.estado === "recogida" || o.estado === "rechazada" || o.estado === "cancelada")
    .sort((a, b) => ((a.resultado?.ocurrido_at ?? a.created_at) < (b.resultado?.ocurrido_at ?? b.created_at) ? 1 : -1));
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
        {([["todas", "Todas"], ["recogida", "Recogidas"], ["rechazada", "Rechazadas"], ["cancelada", "Canceladas"]] as const).map(([k, t]) => (
          <button key={k} className={`chip-filtro ${filtro === k ? "activo" : ""}`} onClick={() => setFiltro(k)}>{t}</button>
        ))}
      </div>
      {visibles.length === 0 ? <Vacio texto="Aún no hay órdenes cerradas." /> : (
        <ul className="historial">
          {visibles.map((o) => (
            <li key={o.id} className={`estado-${o.estado}`}>
              <Pasaporte orden={o}/>
              <span>{o.ubicacion_operativa}</span>
              <span className="tenue">👤 {o.contacto_nombre ?? "—"} · {o.tipo_servicio_ids.map((id) => servicios.get(id)?.nombre).filter(Boolean).join(", ")}</span>
              <span>
                {o.estado === "recogida" ? "✅ Recogida" : o.estado === "cancelada" ? "🚫 Cancelada por el vecino"
                  : `❌ ${o.resultado?.motivo_rechazo_nombre ?? "Rechazada"}`}
                {o.asignacion && <span className="tenue"> · 🚲 {o.asignacion.recolector_nombre}</span>}
              </span>
              <span className="tenue">{hace(o.resultado?.ocurrido_at ?? o.created_at)}</span>
              <button className="btn" onClick={() => onAccion({ tipo: "detalle", orden: o })}>Ver detalle</button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// ------------------------------------------------------------------ reportes (quejas y «hablar con alguien»)

export function VistaReportes({
  casos,
  onRespondido,
  onConflicto,
}: {
  casos: Caso[];
  onRespondido: (c: Caso) => void;
  onConflicto: (e: ErrorApi) => void;
}) {
  const abiertos = casos.filter((c) => c.estado === "abierto").sort((a, b) => (a.created_at < b.created_at ? -1 : 1));
  const atendidos = casos.filter((c) => c.estado === "atendido");
  return (
    <div className="columnas">
      <section>
        <h2>Por responder <span className="tenue">({abiertos.length})</span></h2>
        {abiertos.length ? abiertos.map((c) => <TarjetaCaso key={c.id} caso={c} onRespondido={onRespondido} onConflicto={onConflicto} />)
          : <Vacio texto="No hay reportes pendientes. Cuando un vecino reporte algo o pida hablar con alguien, aparece aquí." />}
      </section>
      <section>
        <h2>Respondidos <span className="tenue">({atendidos.length})</span></h2>
        {atendidos.length ? atendidos.map((c) => <TarjetaCaso key={c.id} caso={c} onRespondido={onRespondido} onConflicto={onConflicto} />)
          : <Vacio texto="Aún no hay reportes respondidos." />}
      </section>
    </div>
  );
}

function TarjetaCaso({ caso: c, onRespondido, onConflicto }: { caso: Caso; onRespondido: (c: Caso) => void; onConflicto: (e: ErrorApi) => void }) {
  const [respuesta, setRespuesta] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [clave] = useState(() => claveParaEnvio());

  async function responder(e: FormEvent) {
    e.preventDefault();
    const texto = respuesta.trim();
    if (!texto) return;
    setEnviando(true);
    setError(null);
    try {
      onRespondido(await api.responderCaso(c, texto, clave({ caso: c.id, version: c.version, texto })));
    } catch (err) {
      if (err instanceof ErrorApi && err.ordenCambio) onConflicto(err);
      else setError((err as Error).message);
    } finally {
      setEnviando(false);
    }
  }

  return (
    <article className={`tarjeta caso caso-${c.estado}`}>
      <div className="tarjeta-cabeza">
        <span className="codigo">{c.codigo} · {c.tipo === "queja" ? "⚠ Reporte" : "🙋 Quiere hablar con alguien"}</span>
        <span className="tenue">{hace(c.created_at)}</span>
      </div>
      <div className="fila-datos">
        <span>👤 {c.contacto_nombre ?? "Vecino"}</span>
        {c.ubicacion && <span>📍 {c.ubicacion}</span>}
        {c.codigo_pasaporte && <span className="chip">{c.codigo_pasaporte}</span>}
      </div>
      <blockquote className="relato">«{c.texto}»</blockquote>
      {c.estado === "atendido" ? (
        <div className="nota">💬 {c.respuesta}</div>
      ) : (
        <form className="responder" onSubmit={responder}>
          <label className="campo">
            Respuesta (le llega por WhatsApp)
            <textarea value={respuesta} onChange={(e) => setRespuesta(e.target.value)} maxLength={1000} rows={2}
              placeholder="Ej.: Rosa pasa mañana entre 8 y 10 am. Disculpa la demora." />
          </label>
          {error && <p className="error" role="alert">{error}</p>}
          <button className="btn primario" disabled={enviando || !respuesta.trim()}>{enviando ? "Enviando…" : "💬 Responder"}</button>
        </form>
      )}
    </article>
  );
}

function Vacio({ texto }: { texto: string }) {
  return <p className="vacio">{texto}</p>;
}
