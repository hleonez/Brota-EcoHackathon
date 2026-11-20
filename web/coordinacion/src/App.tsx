import { useEffect, useState, type FormEvent } from "react";
import { api, cuandoExpire, ErrorApi, fijarToken } from "./api";
import Indicadores from "./Indicadores";
import Administracion from "./Administracion";
import Comunidad from "./Comunidad";
import { Aliados, Marca, Marco } from "./portal";
import Panel from "./Panel";
import type { Sesion } from "./tipos";
import { guardarSesion, leerSesion } from "./util";

export default function App() {
  const [sesion, setSesion] = useState<Sesion | null>(() => leerSesion());
  const [comunidad, setComunidad] = useState(false);
  const [perfil, setPerfil] = useState("");
  const [pagina, setPagina] = useState<"cuenta" | "vencida" | null>(() => {
    const guardada = leerSesion(true);
    return guardada && guardada.expira <= Date.now() ? "vencida" : null;
  });
  fijarToken(sesion?.token ?? null); // antes de que el panel pida datos

  useEffect(() => {
    cuandoExpire(() => {
      guardarSesion(null);
      setSesion(null);
      setPagina("vencida");
    });
  }, []);

  const cambiar = (s: Sesion | null) => {
    setPerfil("");
    setPagina(null);
    guardarSesion(s);
    setSesion(s);
  };

  useEffect(() => {
    if (!sesion) return;
    const timer = window.setTimeout(() => {
      guardarSesion(null);
      setSesion(null);
      setPagina("vencida");
    }, Math.max(0, sesion.expira - Date.now()));
    return () => window.clearTimeout(timer);
  }, [sesion]);

  if (!sesion && pagina === "vencida")
    return <EstadoAcceso titulo="Sesión vencida" accion="Volver a entrar" volver={() => cambiar(null)}>
      Vuelve a ingresar con tu usuario y PIN.
    </EstadoAcceso>;
  if (!sesion)
    return comunidad ? (
      <Comunidad volver={() => setComunidad(false)} />
    ) : (
      <Login onEntrar={cambiar} comunidad={() => setComunidad(true)} />
    );
  const roles = [...new Set(sesion.cuenta.permisos.map((p) => p.rol))];
  const actual = roles.includes(perfil) ? perfil : roles[0];
  const salir = () => cambiar(null);
  const nombre = sesion.cuenta.nombre;
  if (!actual || !["admin", "coordinacion", "fundacion", "huertero", "reciclador"].includes(actual))
    return <EstadoAcceso titulo="Acceso restringido" accion="Volver al inicio" volver={salir}>
      Consulta con administración para habilitar el acceso de tu cuenta.
    </EstadoAcceso>;
  if (pagina === "cuenta")
    return <Marco titulo="Mi cuenta" nombre={nombre} salir={salir}>
      <section className="eco-tarjeta">
        <dl><dt>Nombre</dt><dd>{nombre}</dd><dt>Perfil activo</dt><dd>{actual}</dd></dl>
        <button className="btn primario" onClick={() => setPagina(null)}>Volver al panel</button>
      </section>
    </Marco>;
  return (
    <>
      <div className="cuenta-barra"><button className="btn" onClick={() => setPagina("cuenta")}>Mi cuenta</button></div>
      {roles.length > 1 && (
        <label className="campos">
          Trabajar como
          <select value={actual} onChange={(e) => setPerfil(e.target.value)}>
            {roles.map((r) => (
              <option key={r}>{r}</option>
            ))}
          </select>
        </label>
      )}
      {actual === "fundacion" ? (
        <Marco titulo="Impacto del programa" nombre={nombre} salir={salir}>
          <Indicadores />
        </Marco>
      ) : actual === "admin" ? (
        <Marco
          titulo={`Hola, ${nombre.split(" ")[0]}`}
          nombre={nombre}
          salir={salir}
        >
          <Administracion />
        </Marco>
      ) : (
        <Panel sesion={sesion} rol={actual} onSalir={salir} />
      )}
    </>
  );
}

function EstadoAcceso({ titulo, accion, volver, children }: {
  titulo: string;
  accion: string;
  volver: () => void;
  children: string;
}) {
  return <main className="login">
    <section className="login-caja">
      <Marca />
      <h1>{titulo}</h1>
      <p>{children}</p>
      <button className="btn primario grande" onClick={volver}>{accion}</button>
    </section>
  </main>;
}

function Login({
  onEntrar,
  comunidad,
}: {
  onEntrar: (s: Sesion) => void;
  comunidad: () => void;
}) {
  const [usuario, setUsuario] = useState("");
  const [pin, setPin] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  async function entrar(e: FormEvent) {
    e.preventDefault();
    setEnviando(true);
    setError(null);
    try {
      const r = await api.iniciarSesion(usuario.trim(), pin);
      onEntrar({
        token: r.token,
        expira: Date.now() + r.expira_en * 1000,
        cuenta: r.cuenta,
      });
    } catch (err) {
      setError(
        err instanceof ErrorApi && err.status === 401
          ? "Usuario o PIN incorrectos."
          : (err as Error).message,
      );
      setPin("");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <main className="login acceso">
      <header className="acceso-cabecera">
        <Marca />
        <h1>Entra a Brota</h1>
        <p className="tenue">Acceso para coordinación, administración y Fundación.</p>
      </header>
      <div className="acceso-columnas">
        <section className="acceso-ilustracion">
          <p>Villas de San Pablo</p>
          <h2>Lo que separas, brota.</h2>
          <img src="/marca/huerta.png" alt="" />
        </section>
        <form className="login-caja" onSubmit={entrar}>
          <h2>Ingresa a tu cuenta</h2>
        <label>
          Usuario
          <input
            value={usuario}
            onChange={(e) => setUsuario(e.target.value)}
            autoComplete="username"
            autoCapitalize="none"
            required
          />
        </label>
        <label>
          PIN
          <input
            value={pin}
            onChange={(e) => setPin(e.target.value.replace(/[^0-9]/g, ""))}
            type="password"
            inputMode="numeric"
            autoComplete="current-password"
            minLength={4}
            maxLength={12}
            required
          />
        </label>
        <div className="teclado-pin" role="group" aria-label="Teclado numérico del PIN">
          {["1", "2", "3", "4", "5", "6", "7", "8", "9", "Borrar", "0", "⌫"].map((tecla) =>
            <button key={tecla} type="button" className="btn" disabled={enviando}
              aria-label={tecla === "⌫" ? "Borrar último dígito" : tecla}
              onClick={() => setPin((actual) => tecla === "Borrar" ? "" : tecla === "⌫" ? actual.slice(0, -1) : (actual + tecla).slice(0, 12))}>
              {tecla}
            </button>
          )}
        </div>
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
        <button className="btn primario grande" disabled={enviando}>
          {enviando ? "Entrando…" : "Entrar"}
        </button>
        <p>¿Olvidaste tu PIN? Pídelo a la administración.</p>
        <button type="button" className="btn" onClick={comunidad}>
          Guía para hogares y negocios
        </button>
        </form>
      </div>
      <Aliados />
    </main>
  );
}
