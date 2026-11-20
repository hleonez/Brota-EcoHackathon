import { useEffect, useMemo, useRef, useState, type FormEvent, type ReactNode } from "react";
import { api, ErrorApi } from "./api";
import type { ItemCatalogo, Orden, Recolector } from "./tipos";
import { claveParaEnvio, franjas, puntos, textoFranja } from "./util";

interface Base {
  orden: Orden;
  onListo: (o: Orden, mensaje: string) => void;
  onConflicto: (e: ErrorApi) => void;
  onCerrar: () => void;
}

export function Modal({ titulo, onCerrar, children }: { titulo: string; onCerrar: () => void; children: ReactNode }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current!;
    dialog.showModal();
    return () => dialog.close();
  }, []);
  return (
    <dialog className="modal" ref={ref} onCancel={onCerrar} aria-label={titulo}>
        <header>
          <h2>{titulo}</h2>
          <button className="btn icono" onClick={onCerrar} aria-label="Cerrar">✕</button>
        </header>
        {children}
    </dialog>
  );
}

function Resumen({ orden: o }: { orden: Orden }) {
  return (
    <p className="resumen-orden">
      <strong>{o.codigo_pasaporte}</strong> · {o.ubicacion_operativa} · 👤 {o.contacto_nombre ?? "—"}
    </p>
  );
}

/** Envía y traduce los errores: si la orden cambió, la bandeja se recarga. */
function useEnvio(onConflicto: (e: ErrorApi) => void) {
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function enviar(fn: () => Promise<void>) {
    setEnviando(true);
    setError(null);
    try {
      await fn();
    } catch (e) {
      if (e instanceof ErrorApi && e.ordenCambio) onConflicto(e);
      else setError((e as Error).message);
    } finally {
      setEnviando(false);
    }
  }
  return { enviando, error, enviar };
}

// ------------------------------------------------------------------ asignar

export function DialogoAsignar({ orden, recolectores, modo, onListo, onConflicto, onCerrar }: Base & { recolectores: Recolector[]; modo: "asignar" | "programar" | "reasignar" }) {
  const actual = orden.asignacion;
  const opciones = useMemo(() => {
    const disponibles = franjas().filter((f) => modo !== "programar" || f.id !== "SIN");
    if (!actual?.inicio || !actual.fin) return disponibles;
    const inicio = Date.parse(actual.inicio);
    const fin = Date.parse(actual.fin);
    const alternativas = disponibles.filter((f) => !f.inicio || !f.fin || Date.parse(f.inicio) !== inicio || Date.parse(f.fin) !== fin);
    if (modo === "programar") return alternativas;
    return [{ id: "ACTUAL", titulo: textoFranja(actual.inicio, actual.fin), inicio: actual.inicio, fin: actual.fin }, ...alternativas];
  }, [actual, modo]);
  const [recolector, setRecolector] = useState<string | null>(orden.asignacion?.recolector_id ?? null);
  const [franja, setFranja] = useState(modo === "programar" ? "" : actual?.inicio && actual.fin ? "ACTUAL" : "SIN");
  const [forma, setForma] = useState<"llamada" | "recado">(actual?.forma_aviso ?? "llamada");
  const clave = useRef(claveParaEnvio()).current;
  const { enviando, error, enviar } = useEnvio(onConflicto);
  const verbo = { asignar: "Asignar", programar: "Programar", reasignar: "Reasignar" }[modo];

  function confirmar(e: FormEvent) {
    e.preventDefault();
    const r = recolectores.find((x) => x.id === recolector);
    const f = opciones.find((x) => x.id === franja);
    if (!r || !f) return;
    const datos = { recolector_id: r.id, inicio: f.inicio, fin: f.fin, forma_aviso: forma };
    enviar(async () => {
      const o = await api.asignar(orden, datos, clave({ orden: orden.id, version: orden.version, ...datos }));
      const llamar = r.telefono_contacto ? ` Llama a ${r.nombre}: ${r.telefono_contacto}.` : "";
      onListo(o, `✅ ${orden.codigo_pasaporte} asignada a ${r.nombre} (${f.titulo}). Consulta el estado del aviso de WhatsApp.${llamar}`);
    });
  }

  return (
    <Modal titulo={{ asignar: "¿Quién la recoge?", programar: "Programar recolección", reasignar: "Reasignar responsable" }[modo]} onCerrar={onCerrar}>
      <form onSubmit={confirmar}>
        <Resumen orden={orden} />
        {modo !== "programar" && <fieldset>
          <legend>¿Quién la recoge?</legend>
          <div className="opciones">
            {recolectores.length === 0 && <p className="tenue">No hay recolectores activos en tu gremio.</p>}
            {recolectores.map((r) => (
              <label key={r.id} className={`opcion ${recolector === r.id ? "elegida" : ""}`}>
                <input type="radio" name="recolector" value={r.id} checked={recolector === r.id} onChange={() => setRecolector(r.id)} />
                <span className="opcion-titulo">🚲 {r.nombre}</span>
                <span className="tenue">{r.telefono_contacto ?? "sin teléfono"}</span>
              </label>
            ))}
          </div>
        </fieldset>}
        {modo !== "reasignar" && <fieldset>
          <legend>Horario acordado con el vecino</legend>
          {modo === "programar" && actual?.inicio && actual.fin && <p className="tenue">Horario actual: {textoFranja(actual.inicio, actual.fin)}</p>}
          <div className="opciones compactas">
            {opciones.map((f) => (
              <label key={f.id} className={`opcion ${franja === f.id ? "elegida" : ""}`}>
                <input type="radio" name="franja" value={f.id} checked={franja === f.id} onChange={() => setFranja(f.id)} />
                <span className="opcion-titulo">{f.titulo}</span>
              </label>
            ))}
          </div>
        </fieldset>}
        <fieldset>
          <legend>¿Cómo le avisas al recolector?</legend>
          <div className="opciones compactas">
            {([["llamada", "📞 Llamada"], ["recado", "💬 Recado"]] as const).map(([k, t]) => (
              <label key={k} className={`opcion ${forma === k ? "elegida" : ""}`}>
                <input type="radio" name="forma" value={k} checked={forma === k} onChange={() => setForma(k)} />
                <span className="opcion-titulo">{t}</span>
              </label>
            ))}
          </div>
        </fieldset>
        {modo === "reasignar" && <p className="tenue">Horario actual: {textoFranja(actual?.inicio ?? null, actual?.fin ?? null)}</p>}
        {error && <p className="error" role="alert">{error}</p>}
        <div className="pie-modal">
          <button type="button" className="btn grande" onClick={onCerrar}>Cancelar</button>
          <button className="btn primario grande" disabled={!recolector || !franja || enviando || (modo === "reasignar" && recolector === actual?.recolector_id)}>
            {enviando ? "Guardando…" : verbo}
          </button>
        </div>
      </form>
    </Modal>
  );
}

// ------------------------------------------------------------------ cerrar (recogida o rechazada)

export function DialogoCierre({
  orden,
  tipo,
  motivos,
  materiales,
  onListo,
  onConflicto,
  onCerrar,
}: Base & { tipo: "recogida" | "rechazada"; motivos: ItemCatalogo[]; materiales: ItemCatalogo[] }) {
  const [motivo, setMotivo] = useState<string | null>(null);
  const [aceptados,setAceptados]=useState<string[]>([]);
  const [observacion, setObservacion] = useState("");
  const clave = useRef(claveParaEnvio()).current;
  const momento = useRef<{ clave: string; ocurrido: string } | null>(null);
  const { enviando, error, enviar } = useEnvio(onConflicto);
  const rechazo = tipo === "rechazada";

  function confirmar(e: FormEvent) {
    e.preventDefault();
    if (!orden.asignacion?.inicio || !orden.asignacion.fin || (rechazo ? !motivo : !aceptados.length)) return;
    const nota=[!rechazo ? "Materiales aceptados: "+aceptados.join(", ") : "",observacion.trim()].filter(Boolean).join(". ");
    const datos = {
      resultado: tipo,
      ...(rechazo && motivo ? { motivo_rechazo_id: motivo } : {}),
      ...(nota ? { observacion: nota } : {}),
    };
    const k = clave({ orden: orden.id, version: orden.version, ...datos });
    // Un reintento de la misma operación conserva la hora original (misma clave = mismo cuerpo).
    if (momento.current?.clave !== k) momento.current = { clave: k, ocurrido: new Date().toISOString() };
    const ocurrido_at = momento.current.ocurrido;
    enviar(async () => {
      const o = await api.cerrar(orden, { ...datos, ocurrido_at }, k);
      const quien = orden.contacto_nombre ?? "El vecino";
      const texto = rechazo
        ? `❌ ${orden.codigo_pasaporte} rechazada. Consulta el aviso para ${quien}.`
        : o.puntos_otorgados
          ? `✅ ${orden.codigo_pasaporte} recogida. ${quien} ganó +${puntos(o.puntos_otorgados)} puntos.`
          : `✅ ${orden.codigo_pasaporte} recogida.${o.evaluacion_puntos === "requiere_revision" ? " Los puntos quedan en revisión." : ""}`;
      onListo(o, texto);
    });
  }

  return (
    <Modal titulo={rechazo ? "Registrar rechazo" : "Confirmar recogida"} onCerrar={onCerrar}>
      <form onSubmit={confirmar}>
        <Resumen orden={orden} />
        {orden.asignacion && <p className="tenue">🚲 {orden.asignacion.recolector_nombre}</p>}
        {!rechazo && <fieldset><legend>Materiales aceptados</legend>{materiales.map(m=><label className="opcion" key={m.id}><input type="checkbox" checked={aceptados.includes(m.nombre)} onChange={e=>setAceptados(v=>e.target.checked?[...v,m.nombre]:v.filter(x=>x!==m.nombre))}/>{m.nombre}</label>)}</fieldset>}
        {rechazo && (
          <fieldset>
            <legend>¿Por qué no se pudo recoger?</legend>
            <div className="opciones">
              {motivos.map((m) => (
                <label key={m.id} className={`opcion ${motivo === m.id ? "elegida" : ""}`}>
                  <input type="radio" name="motivo" value={m.id} checked={motivo === m.id} onChange={() => setMotivo(m.id)} />
                  <span className="opcion-titulo">{m.nombre}</span>
                </label>
              ))}
            </div>
          </fieldset>
        )}
        <label className="campo">
          Observación (opcional)
          <textarea value={observacion} onChange={(e) => setObservacion(e.target.value)} maxLength={Math.max(0,475-aceptados.join(", ").length)} rows={2} />
        </label>
        <p className="tenue">
          {rechazo
            ? "Brisa le avisa al vecino con un consejo para que la próxima vez sí se pueda llevar."
            : "La API evalúa la regla de puntos al confirmar la entrega. Los valores propuestos requieren validación de la Fundación."}
        </p>
        {error && <p className="error" role="alert">{error}</p>}
        <div className="pie-modal">
          <button type="button" className="btn grande" onClick={onCerrar}>Cancelar</button>
          <button className={`btn grande ${rechazo ? "peligro" : "exito"}`} disabled={(rechazo ? !motivo : !aceptados.length) || enviando}>
            {enviando ? "Guardando…" : rechazo ? "❌ Registrar rechazo" : "✅ Confirmar recogida"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
