import { useEffect, useId, useRef, useState, type CSSProperties, type ReactNode } from "react";
import { Icono } from "./Iconos";
import { useDatos } from "./portal";

export interface EnlacePanel {
  id: string;
  texto: string;
  cantidad?: number;
}

export interface GrupoPanel {
  titulo?: string;
  enlaces: readonly EnlacePanel[];
}

/** Aviso de la campana: qué está pendiente y a qué sección lleva. */
export interface AvisoPanel {
  id: string;
  texto: string;
  destino: string;
  icono?: string;
}

export interface CuentaPanel {
  nombre: string;
  rol: string;
  cambioPerfil?: ReactNode;
  salir: () => void;
  /** Personaje del perfil en el avatar (public/panel/retrato-*.webp) y su cargo junto al nombre. */
  retrato?: string;
  cargo?: string;
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

export function MarcoPanel({ grupos, activo, titulo, contexto, cuenta, navegar, acciones, portada, avisos = [], ilustracionLateral, children }: {
  grupos: readonly GrupoPanel[];
  activo: string;
  titulo: string;
  contexto: string;
  cuenta: CuentaPanel;
  navegar: (id: string) => void;
  acciones?: ReactNode;
  /** Home views render their own greeting; the h1 stays for focus and screen readers. */
  portada?: boolean;
  /** Pendientes propios del perfil (se suman a los contadores del menú en la campana). */
  avisos?: AvisoPanel[];
  /** Ilustración al pie de la barra lateral en lugar de las plantas (por ejemplo, la caneca). */
  ilustracionLateral?: string;
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

  let orden = 0;
  function enlace(item: EnlacePanel) {
    return (
      <li key={item.id} style={{ "--i": orden++ } as CSSProperties}>
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
      <nav id={id} ref={nav} className={"panel-nav" + (ilustracionLateral ? " con-ilustracion" : "")} aria-label="Secciones del panel"
        style={ilustracionLateral ? { "--lateral-imagen": `url("${ilustracionLateral}")` } as CSSProperties : undefined}
        inert={movil && !abierto}
        data-motion="nav" data-state={abierto ? "open" : "closed"}>
        <div className="panel-logo"><MarcaBrota /></div>
        {/* Las opciones se desplazan aquí y se desvanecen antes de llegar a las plantas. */}
        <div className="panel-nav-lista">
          {grupos.map(({ titulo: grupo, enlaces }) => (
            <div className="panel-grupo" key={grupo ?? enlaces[0]?.id}>
              {grupo && <h2>{grupo}</h2>}
              <ul>{enlaces.map(enlace)}</ul>
            </div>
          ))}
        </div>
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
            <SelectorBarrio />
            <Campana avisos={[
              ...grupos.flatMap((g) => g.enlaces)
                .filter((e) => (e.cantidad ?? 0) > 0)
                .map((e) => ({
                  id: "menu-" + e.id,
                  texto: `${e.texto}: ${e.cantidad} pendiente${e.cantidad === 1 ? "" : "s"}`,
                  destino: e.id,
                  icono: e.id,
                })),
              ...avisos,
            ]} navegar={navegar} />
            <button type="button" className={"panel-avatar" + (cuenta.retrato ? " con-retrato" : "")}
              title={`${cuenta.nombre} · ${cuenta.cargo ?? perfil}`}
              aria-label={`Mi cuenta: ${cuenta.nombre}, ${cuenta.cargo ?? perfil}`}
              aria-current={activo === enlaceCuenta.id ? "page" : undefined}
              onClick={() => navegar(enlaceCuenta.id)}>
              {cuenta.retrato ? <>
                <img src={cuenta.retrato} alt="" width={128} height={128} />
                <span className="panel-avatar-texto"><strong>{cuenta.nombre}</strong><small>{cuenta.cargo ?? perfil}</small></span>
                <Icono nombre="abajo" />
              </> : <Icono nombre="cuenta" />}
            </button>
          </div>
        </header>
        <main className="panel-contenido">
          <div className={"panel-titulo" + (portada ? " es-portada" : "")}>
            <h1 ref={encabezado} tabIndex={-1}>{titulo}</h1>
            {acciones}
          </div>
          {/* La vista entra con una transición suave cada vez que cambia la sección. */}
          <div className="panel-vista" key={activo}>
            {activo === enlaceCuenta.id ? <MiCuenta cuenta={cuenta} /> : children}
          </div>
        </main>
      </div>
    </div>
  );
}

/** Saludo de cada inicio (diseño clay): franja menta con la ilustración del perfil a la derecha y,
 *  debajo, las acciones como tarjetas grandes. */
export function Portada({ saludo, texto, imagen, lado = "derecha", mancha = "lila", children }: {
  saludo: string;
  texto: string;
  imagen?: string;
  /** Dónde va el personaje: a la derecha (por defecto) o a la izquierda del saludo. */
  lado?: "derecha" | "izquierda";
  /** Color de la mancha detrás del personaje. */
  mancha?: "lila" | "verde";
  children?: ReactNode;
}) {
  return (
    <>
      <section className={"portada" + (imagen ? " con-imagen" : "") + (lado === "izquierda" ? " imagen-izquierda" : "") + " mancha-" + mancha}>
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
export function TareaPrincipal({ icono, imagen, titulo, texto }: { icono: string; imagen?: string; titulo: string; texto: string }) {
  return (
    <div className={"tarea-principal" + (imagen ? " con-imagen" : "")}>
      {imagen
        ? <img className="tarea-principal-imagen" src={imagen} alt="" />
        : <span className="tarea-principal-icono"><Icono nombre={icono} /></span>}
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

/** Abre y cierra un menú flotante: clic afuera o Escape lo cierran y el foco vuelve al botón. */
function useFlotante() {
  const [abierto, setAbierto] = useState(false);
  const caja = useRef<HTMLDivElement>(null);
  const boton = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (!abierto) return;
    const fuera = (e: PointerEvent) => {
      if (caja.current && !caja.current.contains(e.target as Node)) setAbierto(false);
    };
    const tecla = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setAbierto(false);
        boton.current?.focus();
      }
    };
    document.addEventListener("pointerdown", fuera);
    document.addEventListener("keydown", tecla);
    return () => {
      document.removeEventListener("pointerdown", fuera);
      document.removeEventListener("keydown", tecla);
    };
  }, [abierto]);
  return { abierto, setAbierto, caja, boton };
}

type Conjunto = { id: string; nombre: string; etapa?: string; activo?: boolean };

/** Barrio del programa y sus conjuntos (hoy el piloto tiene uno). Informativo: no filtra datos. */
function SelectorBarrio() {
  const { abierto, setAbierto, caja, boton } = useFlotante();
  const id = useId();
  const conjuntos = useDatos<Conjunto[]>("/v1/conjuntos");
  const primero = conjuntos.datos?.[0];
  const torres = useDatos<unknown[]>(abierto && primero ? `/v1/conjuntos/${primero.id}/torres` : "");
  return (
    <div className="panel-flotante" ref={caja}>
      <button type="button" className="panel-barrio" ref={boton} aria-expanded={abierto} aria-controls={id}
        onClick={() => setAbierto(!abierto)}>
        <Icono nombre="ubicacion" />
        <span>Villas de San Pablo</span>
        <Icono nombre="abajo" className="panel-barrio-flecha" />
      </button>
      {abierto && (
        <div className="panel-globo" id={id} role="dialog" aria-label="Barrio y conjuntos del programa">
          <p className="panel-globo-titulo">Megabarrio Villas de San Pablo</p>
          <p className="panel-globo-nota">Barranquilla · conjuntos del programa</p>
          {conjuntos.error && <p className="panel-globo-nota">No pudimos cargar los conjuntos.</p>}
          {!conjuntos.datos && !conjuntos.error && <p className="panel-globo-nota">Cargando…</p>}
          <ul>
            {conjuntos.datos?.map((c) => (
              <li key={c.id} className="panel-globo-fila es-actual">
                <span className="panel-globo-icono"><Icono nombre="unidades" /></span>
                <span>
                  <strong>{c.nombre}</strong>
                  <small>{c.etapa ?? "Piloto"}{c === primero && torres.datos ? ` · ${torres.datos.length} torres` : ""}</small>
                </span>
                <Icono nombre="check" className="panel-globo-check" />
              </li>
            ))}
          </ul>
          <p className="panel-globo-pie">El piloto opera en este conjunto; los nuevos se suman desde administración.</p>
        </div>
      )}
    </div>
  );
}

/** Campana: junta los pendientes del perfil y lleva a la sección de cada uno. */
function Campana({ avisos, navegar }: { avisos: AvisoPanel[]; navegar: (id: string) => void }) {
  const { abierto, setAbierto, caja, boton } = useFlotante();
  const id = useId();
  const hay = avisos.length > 0;
  const etiqueta = hay
    ? `Notificaciones: ${avisos.length} pendiente${avisos.length === 1 ? "" : "s"}`
    : "Notificaciones: todo al día";
  return (
    <div className="panel-flotante" ref={caja}>
      <button type="button" className={"panel-campana" + (hay ? " con-avisos" : "")} ref={boton}
        aria-expanded={abierto} aria-controls={id} aria-label={etiqueta} title={etiqueta}
        onClick={() => setAbierto(!abierto)}>
        <Icono nombre="campana" />
        {hay && <span className="panel-campana-punto" aria-hidden="true">{avisos.length}</span>}
      </button>
      {abierto && (
        <div className="panel-globo panel-globo-avisos" id={id} role="dialog" aria-label="Notificaciones">
          <p className="panel-globo-titulo">Notificaciones</p>
          {hay ? (
            <ul>
              {avisos.map((a) => (
                <li key={a.id}>
                  <button type="button" className="panel-globo-fila"
                    onClick={() => { setAbierto(false); navegar(a.destino); }}>
                    <span className="panel-globo-icono"><Icono nombre={a.icono ?? "campana"} /></span>
                    <span>{a.texto}</span>
                    <Icono nombre="chevron" className="panel-globo-check" />
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="panel-globo-vacio"><Icono nombre="check" />Todo al día. No hay pendientes.</p>
          )}
        </div>
      )}
    </div>
  );
}
