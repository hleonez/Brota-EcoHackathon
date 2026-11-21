import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { Icono } from "./Iconos";

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

/** Icono del área en la barra superior, por perfil. */
const iconoPerfil: Record<string, string> = {
  admin: "sistema",
  coordinacion: "bandeja",
  fundacion: "indicadores",
  huertero: "hoja",
  reciclador: "reciclar",
};

/** Logo de Brota para fondos oscuros: brote original + nombre en blanco (Poppins) y punto verde hoja. */
export function MarcaBrota() {
  return (
    <span className="marca-brota" role="img" aria-label="Brota">
      <img src="/panel/brote.webp" alt="" width={79} height={69} />
      <span aria-hidden="true">Brota</span>
      <i aria-hidden="true" />
    </span>
  );
}

export function MarcoPanel({ grupos, activo, titulo, contexto, cuenta, navegar, acciones, portada, children }: {
  grupos: readonly GrupoPanel[];
  activo: string;
  titulo: string;
  contexto: string;
  cuenta: CuentaPanel;
  navegar: (id: string) => void;
  acciones?: ReactNode;
  /** Home views render their own greeting; the h1 stays for focus and screen readers. */
  portada?: boolean;
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
          <span className="panel-enlace-texto"><Icono nombre={item.id} />{item.texto}</span>
          {item.cantidad !== undefined && item.cantidad > 0 && (
            <span className="panel-cantidad">{item.cantidad}</span>
          )}
        </button>
      </li>
    );
  }

  const perfil = nombresPerfil[cuenta.rol] ?? cuenta.rol;

  return (
    <div className="portal panel-marco" onKeyDown={(e) => {
      if (abierto && e.key === "Escape") cerrarMenu();
    }}>
      <header className="panel-movil">
        <MarcaBrota />
        <button type="button" className="btn panel-boton-menu" ref={boton} aria-controls={id}
          aria-expanded={abierto} aria-label={abierto ? "Cerrar menú" : "Abrir menú"}
          onClick={() => abierto ? cerrarMenu() : setAbierto(true)}>
          <Icono nombre={abierto ? "cerrar" : "menu"} />
          <span aria-hidden="true">{abierto ? "Cerrar" : "Menú"}</span>
        </button>
      </header>
      {movil && abierto && <div className="panel-velo" aria-hidden="true" onClick={cerrarMenu} />}
      <nav id={id} ref={nav} className="panel-nav" aria-label="Secciones del panel"
        inert={movil && !abierto}
        data-motion="nav" data-state={abierto ? "open" : "closed"}>
        <div className="panel-logo"><MarcaBrota /></div>
        {grupos.map(({ titulo: grupo, enlaces }) => (
          <div className="panel-grupo" key={grupo ?? enlaces[0]?.id}>
            {grupo && <h2>{grupo}</h2>}
            <ul>{enlaces.map(enlace)}</ul>
          </div>
        ))}
      </nav>
      <div className="panel-principal">
        <header className="panel-barra">
          <div className="panel-contexto">
            <span className="panel-contexto-icono"><Icono nombre={iconoPerfil[cuenta.rol] ?? "hoja"} /></span>
            <span className="panel-contexto-texto">
              <strong>{perfil}</strong>
              {perfil !== contexto && <small>{contexto}</small>}
            </span>
          </div>
          <div className="panel-identificacion">
            {cuenta.cambioPerfil}
            <span className="panel-programa">
              <img src="/acceso/ecoconecta.webp" width={660} height={223} alt="EcoConecta Villas de San Pablo" />
            </span>
            <button type="button" className="panel-avatar" title={`${cuenta.nombre} · ${perfil}`}
              aria-label={`Mi cuenta: ${cuenta.nombre}, ${perfil}`}
              aria-current={activo === enlaceCuenta.id ? "page" : undefined}
              onClick={() => navegar(enlaceCuenta.id)}>
              <Icono nombre="cuenta" />
            </button>
          </div>
        </header>
        <main className="panel-contenido">
          <div className={"panel-titulo" + (portada ? " es-portada" : "")}>
            <h1 ref={encabezado} tabIndex={-1}>{titulo}</h1>
            {acciones}
          </div>
          {activo === enlaceCuenta.id ? <MiCuenta cuenta={cuenta} /> : children}
        </main>
      </div>
    </div>
  );
}

/** Saludo de cada inicio (diseño clay): franja menta con la ilustración del perfil a la derecha y,
 *  debajo, las acciones como tarjetas grandes. */
export function Portada({ saludo, texto, imagen, children }: {
  saludo: string;
  texto: string;
  imagen?: string;
  children?: ReactNode;
}) {
  return (
    <>
      <section className={"portada" + (imagen ? " con-imagen" : "")}>
        <span className="portada-chispas" aria-hidden="true" />
        <div className="portada-texto">
          <p className="portada-saludo">{saludo} <span className="portada-mano" aria-hidden="true">👋</span></p>
          <p className="portada-descripcion">{texto}</p>
        </div>
        {imagen && (
          <div className="portada-ilustracion" aria-hidden="true">
            <img className="portada-imagen" src={imagen} alt="" />
          </div>
        )}
      </section>
      {children && <div className="portada-acciones">{children}</div>}
    </>
  );
}

/** Featured task card (organic-flow mockup). Informational: the actions sit next to it. */
export function TareaPrincipal({ icono, titulo, texto }: { icono: string; titulo: string; texto: string }) {
  return (
    <div className="tarea-principal">
      <span className="tarea-principal-icono"><Icono nombre={icono} /></span>
      <div className="tarea-principal-texto">
        <span className="tarea-principal-etiqueta"><Icono nombre="hoja" />Tarea principal de hoy</span>
        <strong>{titulo}</strong>
        <p>{texto}</p>
      </div>
    </div>
  );
}

/** Tones map to manual colors: leaf tint, solar-yellow tint, teal tint, or solid Verde Eco. */
export type TonoAccion = "verde" | "amarillo" | "turquesa" | "lila" | "solido";

export function TarjetaAccion({ icono, imagen, titulo, texto, tono = "verde", onClick }: {
  icono: string;
  /** Ilustración 3D (public/panel/*.webp); sin ella se usa el icono lineal. */
  imagen?: string;
  titulo: string;
  texto?: string;
  tono?: TonoAccion;
  onClick: () => void;
}) {
  return (
    <button type="button" className={"tarjeta-accion tono-" + tono + (imagen ? " con-imagen" : "")} onClick={onClick}>
      {imagen
        ? <img className="tarjeta-accion-imagen" src={imagen} alt="" />
        : <span className="tarjeta-accion-icono"><Icono nombre={icono} /></span>}
      <span className="tarjeta-accion-texto">
        <strong>{titulo}</strong>
        {texto && <span>{texto}</span>}
      </span>
      <span className="tarjeta-accion-flecha"><Icono nombre="chevron" /></span>
    </button>
  );
}

function MiCuenta({ cuenta }: { cuenta: CuentaPanel }) {
  return (
    <section className="eco-tarjeta cuenta-detalle" aria-label="Datos de la sesión">
      <dl>
        <div><dt>Nombre</dt><dd>{cuenta.nombre}</dd></div>
        <div><dt>Perfil activo</dt><dd>{nombresPerfil[cuenta.rol] ?? cuenta.rol}</dd></div>
      </dl>
      <button type="button" className="btn cuenta-salir" onClick={cuenta.salir}>
        <Icono nombre="salir" />Cerrar sesión
      </button>
    </section>
  );
}
