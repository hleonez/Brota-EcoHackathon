import { useRef, useState, type FormEvent, type ReactNode } from "react";
import { ErrorApi, pedir } from "./api";
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
}: {
  titulo: string;
  children: ReactNode;
  preparar: (v: Valores) => Operacion;
  alGuardar: () => void;
  alConflicto?: () => void;
  accion?: string;
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
      <button className="btn primario" disabled={ocupado}>
        {ocupado ? "Guardando…" : accion}
      </button>
      {mensaje && <p role="status">{mensaje}</p>}
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
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
}) {
  return (
    <label>
      {titulo}
      {opciones ? (
        <select name={nombre} required={!opcional} defaultValue="">
          <option value="">
            {opcional ? "Sin seleccionar" : "Selecciona una opción"}
          </option>
          {opciones.map(([id, t]) => (
            <option key={id} value={id}>
              {t}
            </option>
          ))}
        </select>
      ) : tipo === "textarea" ? (
        <textarea required={!opcional} name={nombre} maxLength={maxLength} />
      ) : (
        <input
          name={nombre}
          type={tipo}
          required={!opcional}
          min={min}
          step={step}
          maxLength={maxLength}
          pattern={pattern}
          autoComplete={tipo === "password" ? "new-password" : undefined}
        />
      )}
    </label>
  );
}
