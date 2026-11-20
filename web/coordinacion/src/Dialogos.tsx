import { useEffect, useMemo, useRef, useState, type FormEvent, type ReactNode } from "react";
import { api, ErrorApi } from "./api";
import type { AcuerdoCanal, ItemCatalogo, Orden, Recolector } from "./tipos";
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
    const origen = document.activeElement;
    dialog.showModal();
    return () => {
      dialog.close();
      if (origen instanceof HTMLElement && origen.isConnected) origen.focus();
    };
  }, []);
  return (
    <dialog className="modal" ref={ref} data-motion="dialog" data-state="open"
      onCancel={(e) => { e.preventDefault(); onCerrar(); }} aria-label={titulo}>
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

// ------------------------------------------------------------------ asignar / reasignar (sin horario)

export function DialogoAsignar({ orden, recolectores, modo, onListo, onConflicto, onCerrar }: Base & { recolectores: Recolector[]; modo: "asignar" | "reasignar" }) {
  const actual = orden.asignacion;
  const [recolector, setRecolector] = useState<string | null>(actual?.recolector_id ?? null);
  const [forma, setForma] = useState<"llamada" | "recado">(actual?.forma_aviso ?? "llamada");
  const clave = useRef(claveParaEnvio()).current;
  const { enviando, error, enviar } = useEnvio(onConflicto);
  const verbo = modo === "asignar" ? "Asignar" : "Reasignar";

  function confirmar(e: FormEvent) {
    e.preventDefault();
    const r = recolectores.find((x) => x.id === recolector);
    if (!r) return;
    const datos = { recolector_id: r.id, forma_aviso: forma };
    enviar(async () => {
      const o = await api.asignar(orden, datos, clave({ orden: orden.id, version: orden.version, ...datos }));
      const llamar = r.telefono_contacto ? ` Llama a ${r.nombre}: ${r.telefono_contacto}.` : "";
      onListo(o, `✅ ${orden.codigo_pasaporte} asignada a ${r.nombre}. Falta programar el horario.${llamar}`);
    });
  }

  return (
    <Modal titulo={modo === "asignar" ? "¿Quién la recoge?" : "Reasignar responsable"} onCerrar={onCerrar}>
      <form onSubmit={confirmar}>
        <Resumen orden={orden} />
        <fieldset>
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
        </fieldset>
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
        {modo === "reasignar" && orden.estado === "programada" && <p className="tenue">Al reasignar se pierde el horario ({textoFranja(actual?.inicio ?? null, actual?.fin ?? null)}). Tendrás que programar de nuevo.</p>}
        {error && <p className="error" role="alert">{error}</p>}
        <div className="pie-modal">
          <button type="button" className="btn grande" onClick={onCerrar}>Cancelar</button>
          <button className="btn primario grande" disabled={!recolector || enviando || (modo === "reasignar" && recolector === actual?.recolector_id)}>
            {enviando ? "Guardando…" : verbo}
          </button>
        </div>
      </form>
    </Modal>
  );
}

// ------------------------------------------------------------------ programar / reprogramar

export function DialogoProgramar({ orden, onListo, onConflicto, onCerrar }: Base) {
  const actual = orden.asignacion;
  const opciones = useMemo(() => {
    const todas = franjas().filter((f) => f.inicio && f.fin);
    if (!actual?.inicio || !actual.fin) return todas;
    const i = Date.parse(actual.inicio);
    const f = Date.parse(actual.fin);
    return todas.filter((x) => Date.parse(x.inicio!) !== i || Date.parse(x.fin!) !== f);
  }, [actual]);
  const [franja, setFranja] = useState("");
  const [canal, setCanal] = useState<AcuerdoCanal | "">("");
  const [observacion, setObservacion] = useState("");
  const clave = useRef(claveParaEnvio()).current;
  const { enviando, error, enviar } = useEnvio(onConflicto);
  const reprograma = orden.estado === "programada";

  function confirmar(e: FormEvent) {
    e.preventDefault();
    const f = opciones.find((x) => x.id === franja);
    if (!f?.inicio || !f.fin || !canal) return;
    const nota = observacion.trim();
    const datos = { inicio: f.inicio, fin: f.fin, acuerdo_canal: canal, ...(nota ? { acuerdo_observacion: nota } : {}) };
    enviar(async () => {
      const o = await api.programar(orden, datos, clave({ orden: orden.id, version: orden.version, ...datos }));
      onListo(o, `✅ ${orden.codigo_pasaporte} ${reprograma ? "reprogramada" : "programada"}: ${f.titulo}. Consulta el estado del aviso de WhatsApp.`);
    });
  }

  return (
    <Modal titulo={reprograma ? "Reprogramar recolección" : "Programar recolección"} onCerrar={onCerrar}>
      <form onSubmit={confirmar}>
        <Resumen orden={orden} />
        {actual && <p className="tenue">🚲 {actual.recolector_nombre}{reprograma && ` · horario actual: ${textoFranja(actual.inicio, actual.fin)}`}</p>}
        {orden.preferencia_horaria && <p className="tenue">🕒 Preferencia del vecino: {orden.preferencia_horaria}</p>}
        <fieldset>
          <legend>Horario acordado con el vecino</legend>
          <div className="opciones compactas">
            {opciones.map((f) => (
              <label key={f.id} className={`opcion ${franja === f.id ? "elegida" : ""}`}>
                <input type="radio" name="franja" value={f.id} checked={franja === f.id} onChange={() => setFranja(f.id)} />
                <span className="opcion-titulo">{f.titulo}</span>
              </label>
            ))}
          </div>
        </fieldset>
        <fieldset>
          <legend>¿Cómo se acordó?</legend>
          <div className="opciones compactas">
            {([["whatsapp", "💬 WhatsApp"], ["llamada", "📞 Llamada"], ["presencial", "🤝 Presencial"]] as const).map(([k, t]) => (
              <label key={k} className={`opcion ${canal === k ? "elegida" : ""}`}>
                <input type="radio" name="canal" value={k} checked={canal === k} onChange={() => setCanal(k)} />
                <span className="opcion-titulo">{t}</span>
              </label>
            ))}
          </div>
        </fieldset>
        <label className="campo">
          Observación del acuerdo (opcional)
          <textarea value={observacion} onChange={(e) => setObservacion(e.target.value)} maxLength={300} rows={2} />
        </label>
        {error && <p className="error" role="alert">{error}</p>}
        <div className="pie-modal">
          <button type="button" className="btn grande" onClick={onCerrar}>Cancelar</button>
          <button className="btn primario grande" disabled={!franja || !canal || enviando}>
            {enviando ? "Guardando…" : reprograma ? "Reprogramar" : "Programar"}
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
    if (orden.estado !== "programada" || (rechazo ? !motivo : !aceptados.length)) return;
    const nota = observacion.trim();
    const datos = {
      resultado: tipo,
      materiales_confirmados: rechazo ? [] : aceptados, // UUID del catálogo del gremio
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
        {!rechazo && <fieldset><legend>Materiales aceptados</legend>{materiales.map(m=><label className="opcion" key={m.id}><input type="checkbox" checked={aceptados.includes(m.id)} onChange={e=>setAceptados(v=>e.target.checked?[...v,m.id]:v.filter(x=>x!==m.id))}/>{m.nombre}</label>)}</fieldset>}
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
          <textarea value={observacion} onChange={(e) => setObservacion(e.target.value)} maxLength={500} rows={2} />
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
