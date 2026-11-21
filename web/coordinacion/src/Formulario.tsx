import { useRef, useState, type FormEvent, type ReactNode } from "react";
import { ErrorApi, pedir } from "./api";
import { Estado } from "./portal";
import { claveParaEnvio } from "./util";

export type Valores = Record<string, string>;
export interface Operacion {
  ruta: string;
  cuerpo: unknown;
  metodo?: "POST" | "PATCH";
}
export function Formulario({
  titulo,
  children,
  preparar,
  alGuardar,
  alConflicto,
  accion = "Guardar",
  alVolver,
}: {
  titulo: string;
  children: ReactNode;
  preparar: (v: Valores) => Operacion;
  alGuardar: () => void;
  alConflicto?: () => void;
  accion?: string;
  /** When editing a selected record: shows "Volver" next to the submit button. */
  alVolver?: () => void;
}) {
  const [mensaje, setMensaje] = useState("");
  const [error, setError] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const ocupadoRef = useRef(false);
  const clave = useRef(claveParaEnvio());
  async function enviar(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (ocupadoRef.current) return;
    ocupadoRef.current = true;
    setOcupado(true);
    setError("");
    setMensaje("");
    const form = e.currentTarget;
    try {
      const datos = Object.fromEntries(new FormData(form)) as Valores;
      const operacion = preparar(datos);
      await pedir(operacion.metodo || "POST", "/v1/" + operacion.ruta, {
        cuerpo: operacion.cuerpo,
        clave: clave.current(operacion),
      });
      if (!form.isConnected) return;
      clave.current = claveParaEnvio();
      form.reset();
      setMensaje("Cambios guardados.");
      alGuardar();
    } catch (e) {
      if (!form.isConnected) return;
      setError((e as Error).message);
      if (e instanceof ErrorApi && e.codigo === "VERSION_CONFLICT") alConflicto?.();
    } finally {
      ocupadoRef.current = false;
      if (form.isConnected) setOcupado(false);
    }
  }
  return (
    <form className="eco-tarjeta formulario" onSubmit={enviar}>
      <h2>{titulo}</h2>
      {children}
      <div className="formulario-acciones">
        {alVolver && <button type="button" className="btn" onClick={alVolver}>Volver</button>}
        <button className="btn primario" disabled={ocupado}>
          {ocupado ? "Guardando…" : accion}
        </button>
      </div>
      {mensaje && <Estado tipo="exito">{mensaje}</Estado>}
      {error && <Estado tipo="error">{error}</Estado>}
    </form>
  );
}
export function Campo({
  nombre,
  titulo,
  tipo = "text",
  opciones,
  opcional = false,
  min,
  step,
  maxLength,
  pattern,
  valorInicial,
}: {
  nombre: string;
  titulo: string;
  tipo?: string;
  opciones?: [string, string][];
  opcional?: boolean;
  min?: number;
  step?: string;
  maxLength?: number;
  pattern?: string;
  valorInicial?: string;
}) {
  const inicial = valorInicial ?? "";
  // Short required choices read better as pills than as a dropdown.
  if (opciones && !opcional && opciones.length > 0 && opciones.length <= MAX_PILDORAS)
    return <Pildoras nombre={nombre} titulo={titulo} opciones={opciones} valorInicial={inicial} />;
  return (
    <label>
      {titulo}
      {opciones ? (
        <select name={nombre} required={!opcional} defaultValue={inicial}>
          {opcional
            ? <option value="">Sin seleccionar</option>
            : <option value="" disabled hidden>Selecciona una opción</option>}
          {opciones.map(([id, t]) => (
            <option key={id} value={id}>
              {t}
            </option>
          ))}
        </select>
      ) : tipo === "textarea" ? (
        <textarea required={!opcional} name={nombre} maxLength={maxLength} defaultValue={inicial} />
      ) : (
        <input
          name={nombre}
          type={tipo}
          required={!opcional}
          min={min}
          step={step}
          maxLength={maxLength}
          pattern={pattern}
          defaultValue={inicial}
          autoComplete={tipo === "password" ? "new-password" : undefined}
        />
      )}
    </label>
  );
}

const MAX_PILDORAS = 3;

/** Single choice shown as pill buttons (native radios, so FormData and validation still work). */
export function Pildoras({
  nombre,
  titulo,
  opciones,
  valorInicial = "",
  onChange,
}: {
  nombre: string;
  titulo: string;
  opciones: [string, string][];
  valorInicial?: string;
  onChange?: (valor: string) => void;
}) {
  const marcado = valorInicial || (opciones.length === 1 ? opciones[0][0] : "");
  return (
    <fieldset className="pildoras">
      <legend>{titulo}</legend>
      <div className="pildoras-opciones">
        {opciones.map(([id, texto]) => (
          <label key={id} className="pildora">
            <input type="radio" name={nombre} value={id} required defaultChecked={marcado === id}
              onChange={onChange && ((e) => e.target.checked && onChange(id))} />
            <span>{texto}</span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}

/** Two-step deactivate button: the first click asks, the second one confirms. */
export function BotonBaja({ texto, alConfirmar }: { texto: string; alConfirmar: () => Promise<void> }) {
  const [paso, setPaso] = useState<"inicio" | "confirmar" | "enviando">("inicio");
  if (paso === "inicio")
    return <button className="btn btn-sm peligro" onClick={() => setPaso("confirmar")}>{texto}</button>;
  return (
    <span className="confirmar-baja" role="group" aria-label={`Confirmar: ${texto.toLowerCase()}`}>
      <button className="btn btn-sm peligro-solido" disabled={paso === "enviando"} autoFocus
        onClick={async () => { setPaso("enviando"); await alConfirmar(); setPaso("inicio"); }}>
        {paso === "enviando" ? "…" : "Sí, " + texto.toLowerCase()}
      </button>
      <button className="btn btn-sm" onClick={() => setPaso("inicio")}>Cancelar</button>
    </span>
  );
}
