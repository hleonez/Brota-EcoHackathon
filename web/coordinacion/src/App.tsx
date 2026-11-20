import { useEffect, useState, type FormEvent } from "react";
import { api, cuandoExpire, ErrorApi, fijarToken } from "./api";
import Panel from "./Panel";
import type { Sesion } from "./tipos";
import { guardarSesion, leerSesion } from "./util";

export default function App() {
  const [sesion, setSesion] = useState<Sesion | null>(leerSesion);
  fijarToken(sesion?.token ?? null); // antes de que el panel pida datos

  useEffect(() => {
    cuandoExpire(() => {
      guardarSesion(null);
      setSesion(null);
    });
  }, []);

  const cambiar = (s: Sesion | null) => {
    guardarSesion(s);
    setSesion(s);
  };

  return sesion ? <Panel sesion={sesion} onSalir={() => cambiar(null)} /> : <Login onEntrar={cambiar} />;
}

function Login({ onEntrar }: { onEntrar: (s: Sesion) => void }) {
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
      onEntrar({ token: r.token, expira: Date.now() + r.expira_en * 1000, cuenta: r.cuenta });
    } catch (err) {
      setError(err instanceof ErrorApi && err.status === 401 ? "Usuario o PIN incorrectos." : (err as Error).message);
      setPin("");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <main className="login">
      <form className="login-caja" onSubmit={entrar}>
        <div className="marca">🌱 Brota</div>
        <h1>Panel de coordinación</h1>
        <p className="tenue">Solicitudes, recolectores y cierres del día.</p>
        <label>
          Usuario
          <input value={usuario} onChange={(e) => setUsuario(e.target.value)} autoComplete="username" autoCapitalize="none" required />
        </label>
        <label>
          PIN
          <input
            value={pin}
            onChange={(e) => setPin(e.target.value)}
            type="password"
            inputMode="numeric"
            autoComplete="current-password"
            minLength={4}
            maxLength={12}
            required
          />
        </label>
        {error && <p className="error" role="alert">{error}</p>}
        <button className="btn primario grande" disabled={enviando}>
          {enviando ? "Entrando…" : "Entrar"}
        </button>
      </form>
    </main>
  );
}
