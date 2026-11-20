import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { Marca } from "./portal";

export interface EnlacePanel {
  id: string;
  texto: string;
  cantidad?: number;
}

export interface GrupoPanel {
  titulo?: string;
  enlaces: readonly EnlacePanel[];
}

export interface CuentaPanel {
  nombre: string;
  rol: string;
  cambioPerfil?: ReactNode;
  salir: () => void;
}

export const nombresPerfil: Record<string, string> = {
  admin: "Administración",
  coordinacion: "Coordinación",
  fundacion: "Fundación",
  reciclador: "Reciclador",
  huertero: "Huertero",
};

export const enlaceCuenta = { id: "cuenta", texto: "Mi cuenta" } as const;

export function MarcoPanel({ grupos, activo, titulo, contexto, cuenta, navegar, acciones, children }: {
  grupos: readonly GrupoPanel[];
  activo: string;
  titulo: string;
  contexto: string;
  cuenta: CuentaPanel;
  navegar: (id: string) => void;
  acciones?: ReactNode;
  children: ReactNode;
}) {
  const [abierto, setAbierto] = useState(false);
  const [movil, setMovil] = useState(() => window.matchMedia("(max-width: 1023px)").matches);
  useEffect(() => {
    const media = window.matchMedia("(max-width: 1023px)");
    const actualizar = () => setMovil(media.matches);
    media.addEventListener("change", actualizar);
    return () => media.removeEventListener("change", actualizar);
  }, []);
  const id = useId();
  const nav = useRef<HTMLElement>(null);
  const boton = useRef<HTMLButtonElement>(null);
  const encabezado = useRef<HTMLHeadingElement>(null);
  const enfocarTitulo = useRef(false);

  useEffect(() => {
    if (abierto) {
      const menu = nav.current;
      (menu?.querySelector<HTMLButtonElement>('[aria-current="page"]') ??
        menu?.querySelector<HTMLButtonElement>("button"))?.focus();
    }
  }, [abierto]);

  useEffect(() => {
    if (enfocarTitulo.current) {
      encabezado.current?.focus();
      enfocarTitulo.current = false;
    }
  }, [activo, abierto]);

  function cerrarMenu() {
    setAbierto(false);
    boton.current?.focus();
  }

  function enlace(item: EnlacePanel) {
    return (
      <li key={item.id}>
        <button type="button" className="panel-enlace"
          aria-current={activo === item.id ? "page" : undefined}
          onClick={() => {
            if (abierto) enfocarTitulo.current = true;
            setAbierto(false);
            navegar(item.id);
          }}>
          {item.texto}
          {item.cantidad !== undefined && item.cantidad > 0 && (
            <span className="panel-cantidad">{item.cantidad}</span>
          )}
        </button>
      </li>
    );
  }

  return (
    <div className="portal panel-marco" onKeyDown={(e) => {
      if (abierto && e.key === "Escape") cerrarMenu();
    }}>
      <header className="panel-barra">
        <Marca />
        <div className="panel-identificacion">
          <span>{contexto}</span>
          {cuenta.cambioPerfil}
        </div>
      </header>
      <div className="panel-menu">
        <span>{titulo}</span>
        <button type="button" className="btn" ref={boton} aria-controls={id}
          aria-expanded={abierto} onClick={() => abierto ? cerrarMenu() : setAbierto(true)}>
          {abierto ? "Cerrar menú" : "Abrir menú"}
        </button>
      </div>
      <nav id={id} ref={nav} className="panel-nav" aria-label="Secciones del panel"
        inert={movil && !abierto}
        data-motion="nav" data-state={abierto ? "open" : "closed"}>
        {grupos.map(({ titulo: grupo, enlaces }) => (
          <div className="panel-grupo" key={grupo ?? enlaces[0]?.id}>
            {grupo && <h2>{grupo}</h2>}
            <ul>{enlaces.map(enlace)}</ul>
          </div>
        ))}
        <div className="panel-grupo panel-cuenta">
          <h2>Configuración de cuenta</h2>
          <ul>{enlace(enlaceCuenta)}</ul>
          <button className="panel-enlace" type="button" onClick={cuenta.salir}>Cerrar sesión</button>
        </div>
      </nav>
      <main className="panel-contenido">
        <div className="panel-titulo">
          <h1 ref={encabezado} tabIndex={-1}>{titulo}</h1>
          {acciones}
        </div>
        {activo === enlaceCuenta.id ? <MiCuenta cuenta={cuenta} /> : children}
      </main>
    </div>
  );
}

function MiCuenta({ cuenta }: { cuenta: CuentaPanel }) {
  return (
    <section className="eco-tarjeta cuenta-detalle" aria-label="Datos de la sesión">
      <dl>
        <div><dt>Nombre</dt><dd>{cuenta.nombre}</dd></div>
        <div><dt>Perfil activo</dt><dd>{nombresPerfil[cuenta.rol] ?? cuenta.rol}</dd></div>
      </dl>
    </section>
  );
}
