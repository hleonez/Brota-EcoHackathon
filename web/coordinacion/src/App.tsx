import { useEffect, useState } from "react";
import { cuandoExpire, fijarToken } from "./api";
import { EstadoAcceso, FormularioAcceso, PantallaAcceso } from "./Acceso";
import { CertificadoVerde } from "./AdminExtra";
import Indicadores from "./Indicadores";
import Administracion from "./Administracion";
import Comunidad from "./Comunidad";
import Panel from "./Panel";
import { MarcoPanel, enlaceCuenta, nombresPerfil, type CuentaPanel } from "./MarcoPanel";
import type { Sesion } from "./tipos";
import { guardarSesion, leerSesion } from "./util";

export default function App() {
  const [sesion, setSesion] = useState<Sesion | null>(() => leerSesion());
  const [comunidad, setComunidad] = useState(false);
  const [perfil, setPerfil] = useState("");
  const [pagina, setPagina] = useState<"vencida" | null>(() => {
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

  const cambiar = (s: Sesion | null, recordar = false) => {
    setPerfil("");
    setPagina(null);
    guardarSesion(s, recordar);
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
      Por seguridad cerramos tu sesión. Vuelve a ingresar con tu usuario y contraseña.
    </EstadoAcceso>;
  if (!sesion)
    return comunidad ? (
      <Comunidad volver={() => setComunidad(false)} />
    ) : (
      <PantallaAcceso etiqueta="Iniciar sesión">
        <FormularioAcceso onEntrar={cambiar} comunidad={() => setComunidad(true)} />
      </PantallaAcceso>
    );
  const roles = [...new Set(sesion.cuenta.permisos.map((p) => p.rol))];
  const actual = roles.includes(perfil) ? perfil : roles[0];
  const salir = () => cambiar(null);
  const nombre = sesion.cuenta.nombre;
  if (!actual || !["admin", "coordinacion", "fundacion", "huertero", "reciclador"].includes(actual))
    return <EstadoAcceso titulo="Acceso restringido" accion="Volver al inicio" volver={salir}>
      Consulta con administración para habilitar el acceso de tu cuenta.
    </EstadoAcceso>;
  const cuenta: CuentaPanel = {
    nombre,
    rol: actual,
    salir,
    cambioPerfil: roles.length > 1 && (
      <label className="panel-perfil">
        Trabajar como
        <select value={actual} onChange={(e) => setPerfil(e.target.value)}>
          {roles.map((r) => <option value={r} key={r}>{nombresPerfil[r] ?? r}</option>)}
        </select>
      </label>
    ),
  };
  if (actual === "admin") return <Administracion cuenta={cuenta} />;
  if (actual === "fundacion") return <Fundacion cuenta={cuenta} />;
  return <Panel key={actual} sesion={sesion} cuenta={cuenta} />;
}

const seccionesFundacion = [{ enlaces: [{ id: "impacto", texto: "Impacto del programa" }] }];

function Fundacion({ cuenta }: { cuenta: CuentaPanel }) {
  const [activo, navegar] = useState("impacto");
  return (
    <MarcoPanel grupos={seccionesFundacion} activo={activo} navegar={navegar} cuenta={cuenta}
      contexto="Fundación Santo Domingo" titulo={activo === enlaceCuenta.id ? enlaceCuenta.texto : "Impacto del programa"}>
      <CertificadoVerde />
      <Indicadores />
    </MarcoPanel>
  );
}
