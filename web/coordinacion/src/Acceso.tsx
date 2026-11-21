/**
 * Entrada al panel (coordinación, recolectores, fundación y administración).
 *
 * Diseño: escena ilustrada de Brota a la izquierda y tarjeta de ingreso a la derecha. En pantallas
 * anchas todo se dibuja sobre un lienzo de 1672×941 unidades (`--u`) para calzar con la ilustración;
 * en móvil y tablet vertical se apila (primero el formulario).
 *
 * Identidad (manual EcoConecta): logo de EcoConecta original, ≥220 px y sobre fondo claro; Poppins
 * en títulos, Inter en texto; colores `--eco-*`; etiquetas visibles y errores con icono y texto.
 *
 * Seguridad: la contraseña (PIN) nunca se guarda; «Recordarme» solo recuerda el usuario y deja la
 * sesión en localStorage hasta que el token vence. Los errores no dicen si el usuario existe.
 */
import { useId, useState, type FormEvent, type ReactNode } from "react";
import { api, ErrorApi } from "./api";
import type { Sesion } from "./tipos";
import { recordarUsuario, usuarioRecordado } from "./util";

const WHATSAPP = String(import.meta.env.VITE_WHATSAPP_NUMERO || "").replace(/\D/g, "");

export function PantallaAcceso({ etiqueta, children }: { etiqueta: string; children: ReactNode }) {
  return (
    <main className="acceso">
      <div className="acceso-lienzo">
        <img className="acceso-fondo" src="/acceso/fondo.webp" alt="" aria-hidden="true" draggable={false} />
        <header className="acceso-marcas">
          <img className="acceso-logo" src="/acceso/logo-brota.webp" alt="Brota" width={291} height={69} />
          <img className="acceso-ecoconecta" src="/acceso/ecoconecta.webp" width={660} height={223}
            alt="EcoConecta Villas de San Pablo" />
        </header>
        <div className="acceso-saludo">
          <h1>Bienvenido a Brota</h1>
          <p>
            <span className="acceso-resaltado">Ingresa para</span> gestionar recolecciones, huerta e
            impacto comunitario.
          </p>
        </div>
        <section className="acceso-tarjeta" aria-label={etiqueta} data-motion="enter">
          <p className="acceso-chip">
            <Chispas />
            <span className="acceso-chip-texto">
              <IconoGrupo />
              Coordinadores, recolectores y administradores
            </span>
            <Chispas espejo />
          </p>
          {children}
        </section>
        <footer className="acceso-aliados">
          <span>Una iniciativa con</span>
          <img src="/marca/fundacion.png" alt="Fundación Santo Domingo" />
          <img src="/marca/villas.png" alt="Villas de San Pablo" />
          <strong>Universidad Libre</strong>
        </footer>
        <img className="acceso-escena" src="/acceso/escena.webp" alt="" aria-hidden="true" draggable={false} />
      </div>
    </main>
  );
}

export function FormularioAcceso({
  onEntrar,
  comunidad,
}: {
  onEntrar: (s: Sesion, recordar: boolean) => void;
  comunidad: () => void;
}) {
  const [usuario, setUsuario] = useState(() => usuarioRecordado());
  const [clave, setClave] = useState("");
  const [recordar, setRecordar] = useState(() => usuarioRecordado() !== "");
  const [verClave, setVerClave] = useState(false);
  const [aviso, setAviso] = useState<{ tipo: "error" | "info"; texto: string } | null>(null);
  const [enviando, setEnviando] = useState(false);
  const idAviso = useId();

  async function entrar(e: FormEvent) {
    e.preventDefault();
    const u = usuario.trim();
    if (!u || clave.length < 4) {
      setAviso({ tipo: "error", texto: "Escribe tu usuario y tu contraseña (mínimo 4 caracteres)." });
      return;
    }
    setEnviando(true);
    setAviso(null);
    try {
      const r = await api.iniciarSesion(u, clave);
      recordarUsuario(recordar ? u : null);
      onEntrar({ token: r.token, expira: Date.now() + r.expira_en * 1000, cuenta: r.cuenta }, recordar);
    } catch (err) {
      setClave("");
      setVerClave(false);
      setAviso({ tipo: "error", texto: mensajeDeError(err) });
    } finally {
      setEnviando(false);
    }
  }

  const describe = aviso ? idAviso : undefined;
  return (
    <form className="acceso-form" onSubmit={entrar} noValidate aria-busy={enviando}>
      <Campo icono={<IconoSobre />} etiqueta="Correo o usuario">
        <input
          value={usuario}
          onChange={(e) => setUsuario(e.target.value)}
          placeholder=" "
          autoComplete="username"
          autoCapitalize="none"
          autoCorrect="off"
          spellCheck={false}
          maxLength={60}
          required
          aria-describedby={describe}
          aria-invalid={aviso?.tipo === "error" || undefined}
        />
      </Campo>
      <Campo
        icono={<IconoCandado />}
        etiqueta="Contraseña"
        extra={
          <button type="button" className="acceso-ojo" onClick={() => setVerClave((v) => !v)}
            aria-label={verClave ? "Ocultar contraseña" : "Mostrar contraseña"} aria-pressed={verClave}>
            {verClave ? <IconoOjoTachado /> : <IconoOjo />}
          </button>
        }
      >
        <input
          value={clave}
          onChange={(e) => setClave(e.target.value)}
          placeholder=" "
          type={verClave ? "text" : "password"}
          autoComplete="current-password"
          maxLength={12}
          required
          aria-describedby={describe}
          aria-invalid={aviso?.tipo === "error" || undefined}
        />
      </Campo>
      <div className="acceso-opciones">
        <label className="acceso-recordar">
          <input type="checkbox" checked={recordar} onChange={(e) => setRecordar(e.target.checked)} />
          <span className="acceso-check" aria-hidden="true"><IconoCheck /></span>
          Recordarme
        </label>
        <button type="button" className="acceso-olvido"
          onClick={() => setAviso({ tipo: "info", texto: "Pídele a la administración de EcoConecta una contraseña nueva. Por seguridad, nadie más puede verla ni cambiarla." })}>
          ¿Olvidaste tu contraseña?
        </button>
      </div>
      <button className="acceso-entrar" disabled={enviando}>
        <IconoEntrar />
        {enviando ? "Entrando…" : "Iniciar sesión"}
      </button>
      <div className="acceso-pie">
        {aviso && (
          <p id={idAviso} className={`acceso-aviso acceso-aviso-${aviso.tipo}`} role={aviso.tipo === "error" ? "alert" : "status"}>
            {aviso.tipo === "error" ? <IconoAlerta /> : <IconoInfo />}
            <span>{aviso.texto}</span>
          </p>
        )}
        <p className="acceso-vecinos">
          ¿Eres vecino o negocio?{" "}
          {WHATSAPP && <><a href={`https://wa.me/${WHATSAPP}`} target="_blank" rel="noopener noreferrer">Pide por WhatsApp</a>{" · "}</>}
          <button type="button" onClick={comunidad}>Guía para hogares y negocios</button>
        </p>
      </div>
    </form>
  );
}

export function EstadoAcceso({ titulo, accion, volver, children }: {
  titulo: string;
  accion: string;
  volver: () => void;
  children: ReactNode;
}) {
  return (
    <PantallaAcceso etiqueta={titulo}>
      <div className="acceso-estado">
        <h2>{titulo}</h2>
        <p>{children}</p>
        <button className="acceso-entrar" onClick={volver}><IconoEntrar />{accion}</button>
      </div>
    </PantallaAcceso>
  );
}

function mensajeDeError(err: unknown): string {
  if (err instanceof ErrorApi) {
    if (err.status === 401) return "Usuario o contraseña incorrectos. Revísalos e inténtalo de nuevo.";
    if (err.status === 429) return err.message;
    if (err.status === 422) return "Revisa el usuario y la contraseña (la contraseña tiene de 4 a 12 caracteres).";
    if (err.status === 0 || err.status >= 500) return "No pudimos conectar con Brota. Revisa tu internet e inténtalo en un momento.";
    return err.message;
  }
  return "No pudimos iniciar sesión. Inténtalo de nuevo.";
}

function Campo({ icono, etiqueta, extra, children }: {
  icono: ReactNode;
  etiqueta: string;
  extra?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="acceso-campo">
      <span className="acceso-campo-icono" aria-hidden="true">{icono}</span>
      <label className="acceso-campo-control">
        {children}
        <span className="acceso-campo-etiqueta">{etiqueta}</span>
      </label>
      {extra}
    </div>
  );
}

// ------------------------------------------------------------------ iconos (trazo lineal, un solo estilo)

const trazo = { fill: "none", stroke: "currentColor", strokeWidth: 2.2, strokeLinecap: "round", strokeLinejoin: "round" } as const;

function IconoSobre() {
  return <svg viewBox="0 0 24 24" {...trazo}><rect x="3" y="5" width="18" height="14" rx="2.5" /><path d="m4 7 8 6 8-6" /></svg>;
}
function IconoCandado() {
  return <svg viewBox="0 0 24 24" {...trazo}><rect x="4.5" y="10.5" width="15" height="10" rx="2.5" /><path d="M8 10.5V8a4 4 0 0 1 8 0v2.5" /><path d="M12 14.5v2.5" /></svg>;
}
function IconoOjo() {
  return <svg viewBox="0 0 24 24" {...trazo}><path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12Z" /><circle cx="12" cy="12" r="3" /></svg>;
}
function IconoOjoTachado() {
  return <svg viewBox="0 0 24 24" {...trazo}><path d="M2.5 12S6 5.5 12 5.5c2 0 3.7.7 5.1 1.7M21.5 12s-3.5 6.5-9.5 6.5c-2 0-3.7-.7-5.1-1.7" /><path d="M9.9 14.1a3 3 0 0 1 4.2-4.2" /><path d="m4 20 16-16" /></svg>;
}
function IconoCheck() {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={3.2} strokeLinecap="round" strokeLinejoin="round"><path d="m5 12.5 4.5 4.5L19 7.5" /></svg>;
}
function IconoEntrar() {
  return <svg viewBox="0 0 24 24" {...trazo} className="acceso-entrar-icono"><path d="M14 4h3.5A2.5 2.5 0 0 1 20 6.5v11a2.5 2.5 0 0 1-2.5 2.5H14" /><path d="M4 12h11" /><path d="m11 8 4 4-4 4" /></svg>;
}
function IconoGrupo() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" className="acceso-chip-icono">
      <circle cx="9" cy="7.5" r="3.6" />
      <path d="M2 19.2c0-3.7 3.1-6.2 7-6.2s7 2.5 7 6.2c0 .6-.4.8-1 .8H3c-.6 0-1-.2-1-.8Z" />
      <circle cx="17" cy="8.5" r="2.9" />
      <path d="M16.2 13.1c3.3-.3 5.8 1.8 5.8 4.9 0 .5-.3.7-.8.7h-3.6c.1-2.1-.4-4-1.4-5.6Z" />
    </svg>
  );
}
function IconoAlerta() {
  return <svg viewBox="0 0 24 24" {...trazo} aria-hidden="true"><path d="M12 4 2.8 19.5h18.4Z" /><path d="M12 10v4.5" /><path d="M12 17.3v.2" /></svg>;
}
function IconoInfo() {
  return <svg viewBox="0 0 24 24" {...trazo} aria-hidden="true"><circle cx="12" cy="12" r="9" /><path d="M12 11v5.5" /><path d="M12 7.7v.2" /></svg>;
}
function Chispas({ espejo = false }: { espejo?: boolean }) {
  return (
    <svg viewBox="0 0 36 58" className={`acceso-chispas${espejo ? " espejo" : ""}`} aria-hidden="true"
      fill="none" stroke="currentColor" strokeWidth={5} strokeLinecap="round">
      <path d="M14 6l12 9" />
      <path d="M4 29.5h25" />
      <path d="M10 52l14-8" />
    </svg>
  );
}
