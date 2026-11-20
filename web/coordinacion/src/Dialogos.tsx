import { useEffect, useMemo, useRef, useState, type FormEvent, type ReactNode } from "react";
import { api, ErrorApi } from "./api";
import type { ItemCatalogo, Orden, Recolector } from "./tipos";
import { claveParaEnvio, franjas, puntos } from "./util";

interface Base {
  orden: Orden;
  onListo: (o: Orden, mensaje: string) => void;
  onConflicto: (e: ErrorApi) => void;
  onCerrar: () => void;
}

function Modal({ titulo, onCerrar, children }: { titulo: string; onCerrar: () => void; children: ReactNode }) {
  useEffect(() => {
    const esc = (e: KeyboardEvent) => e.key === "Escape" && onCerrar();
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, [onCerrar]);
  return (
    <div className="fondo" onClick={(e) => e.target === e.currentTarget && onCerrar()}>
      <div className="modal" role="dialog" aria-modal="true" aria-label={titulo}>
        <header>
          <h2>{titulo}</h2>
          <button className="btn icono" onClick={onCerrar} aria-label="Cerrar">✕</button>
        </header>
        {children}
      </div>
    </div>
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

export function DialogoAsignar({ orden, recolectores, onListo, onConflicto, onCerrar }: Base & { recolectores: Recolector[] }) {
  const opciones = useMemo(() => franjas(), []);
  const [recolector, setRecolector] = useState<string | null>(orden.asignacion?.recolector_id ?? null);
  const [franja, setFranja] = useState(opciones[0].id);
  const [forma, setForma] = useState<"llamada" | "recado">("llamada");
  const clave = useRef(claveParaEnvio()).current;
  const { enviando, error, enviar } = useEnvio(onConflicto);
  const reasignar = orden.estado === "asignada";

  function confirmar(e: FormEvent) {
    e.preventDefault();
    const r = recolectores.find((x) => x.id === recolector);
    const f = opciones.find((x) => x.id === franja)!;
    if (!r) return;
    const datos = { recolector_id: r.id, inicio: f.inicio, fin: f.fin, forma_aviso: forma };
    enviar(async () => {
      const o = await api.asignar(orden, datos, clave({ orden: orden.id, version: orden.version, ...datos }));
      const llamar = r.telefono_contacto ? ` Llama a ${r.nombre}: ${r.telefono_contacto}.` : "";
      onListo(o, `✅ ${orden.codigo_pasaporte} asignada a ${r.nombre} (${f.titulo}). Brisa ya le avisó al vecino.${llamar}`);
    });
  }

  return (
    <Modal titulo={reasignar ? "Reasignar recolección" : "Asignar recolección"} onCerrar={onCerrar}>
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
          <legend>¿Cuándo pasa?</legend>
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
        <p className="tenue">Al confirmar, Brisa le escribe al vecino quién pasa y a qué hora.</p>
        {error && <p className="error" role="alert">{error}</p>}
        <div className="pie-modal">
          <button type="button" className="btn grande" onClick={onCerrar}>Cancelar</button>
          <button className="btn primario grande" disabled={!recolector || enviando}>
            {enviando ? "Asignando…" : reasignar ? "Reasignar" : "Asignar"}
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
  onListo,
  onConflicto,
  onCerrar,
}: Base & { tipo: "recogida" | "rechazada"; motivos: ItemCatalogo[] }) {
  const [motivo, setMotivo] = useState<string | null>(null);
  const [observacion, setObservacion] = useState("");
  const clave = useRef(claveParaEnvio()).current;
  const momento = useRef<{ clave: string; ocurrido: string } | null>(null);
  const { enviando, error, enviar } = useEnvio(onConflicto);
  const rechazo = tipo === "rechazada";

  function confirmar(e: FormEvent) {
    e.preventDefault();
    if (rechazo && !motivo) return;
    const datos = {
      resultado: tipo,
      ...(rechazo && motivo ? { motivo_rechazo_id: motivo } : {}),
      ...(observacion.trim() ? { observacion: observacion.trim() } : {}),
    };
    const k = clave({ orden: orden.id, version: orden.version, ...datos });
    // Un reintento de la misma operación conserva la hora original (misma clave = mismo cuerpo).
    if (momento.current?.clave !== k) momento.current = { clave: k, ocurrido: new Date().toISOString() };
    const ocurrido_at = momento.current.ocurrido;
    enviar(async () => {
      const o = await api.cerrar(orden, { ...datos, ocurrido_at }, k);
      const quien = orden.contacto_nombre ?? "El vecino";
      const texto = rechazo
        ? `❌ ${orden.codigo_pasaporte} rechazada. Brisa le envió a ${quien} un consejo para la próxima.`
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
            : "Brisa le avisa al vecino y le suma sus puntos."}
        </p>
        {error && <p className="error" role="alert">{error}</p>}
        <div className="pie-modal">
          <button type="button" className="btn grande" onClick={onCerrar}>Cancelar</button>
          <button className={`btn grande ${rechazo ? "peligro" : "exito"}`} disabled={(rechazo && !motivo) || enviando}>
            {enviando ? "Guardando…" : rechazo ? "❌ Registrar rechazo" : "✅ Confirmar recogida"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
