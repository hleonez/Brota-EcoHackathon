import { MarcoPanel, Portada, TarjetaAccion, enlaceCuenta, type AvisoPanel, type CuentaPanel } from "./MarcoPanel";
import { useState, type CSSProperties } from "react";
import { Icono } from "./Iconos";
import { pedir } from "./api";
import { BotonBaja, Campo, Formulario, Pildoras, type Operacion, type Valores } from "./Formulario";
import { Espera, Estado, fechaBogota, useDatos } from "./portal";
import { claveNueva } from "./util";
import { temasEducativos, type TemaEducativo } from "./temasEducativos";
import type { Catalogo, ItemCatalogo, Recolector } from "./tipos";
import { Paginada } from "./Paginacion";
import { Modal } from "./Dialogos";
import { Actividad, Conversaciones, LigaTorres, Participantes, Precios, Programa, Reportes, TableroInicio } from "./AdminExtra";

type Fila = {
  id: string;
  version: number;
  nombre?: string;
  usuario?: string;
  activo?: boolean;
  titulo?: string;
  referencia_local?: string;
  codigo?: string;
  vigente_desde?: string;
  recipiente?: string;
  kg_por_unidad?: string;
  parametros?: { puntos?: number };
  vigente_hasta?: string;
  texto?: string;
  permisos?: { rol: string }[];
  estado?: string;
  participante_id?: string;
  unidad_id?: string;
  tema?: TemaEducativo;
  publicado?: boolean;
  trabajador_id?: string | null;
  tipo?: string;
  etiqueta?: string;
  telefono_contacto?: string | null;
};
type ParticipantePiloto = {
  id: string;
  nombre: string;
  unidades: { id: string; tipo: string; etiqueta: string }[];
};

function inicioDiaBogota(fecha: string) {
  return fecha ? fecha + "T00:00:00-05:00" : null;
}

function estadoPiloto(fila: Fila, vinculoVigente: boolean | undefined) {
  if (!fila.activo) return "Inactiva";
  const ahora = Date.now();
  if (fila.vigente_hasta && Date.parse(fila.vigente_hasta) <= ahora) return "Vencida";
  if (fila.vigente_desde && Date.parse(fila.vigente_desde) > ahora) return "Aún no vigente";
  if (vinculoVigente === undefined) return "Vínculo sin verificar";
  return vinculoVigente ? "Vigente" : "Sin vínculo vigente";
}

function estadoContenido(fila: Fila) {
  if (fila.activo === false) return "Retirado";
  const ahora = Date.now();
  const fuera =
    (fila.vigente_hasta && Date.parse(fila.vigente_hasta) <= ahora) ||
    (fila.vigente_desde && Date.parse(fila.vigente_desde) > ahora);
  if (fuera) return "Fuera de vigencia";
  if (fila.publicado === false) return "Borrador";
  return "Publicado";
}

function accionesContenido(fila: Fila): [string, string][] {
  if (fila.activo === false) {
    return [
      ["guardar", "Guardar cambios"],
      ["reactivar", "Reactivar contenido"],
    ];
  }
  // Only the actions that change something: a published item cannot be published again.
  return [
    ["guardar", "Guardar cambios"],
    ...(fila.publicado === false ? [["publicar", "Publicar en la guía"] as [string, string]] : []),
    ["retirar", "Retirar de la guía"],
  ];
}
const gruposAdministracion = [
  { enlaces: ["Inicio"] },
  { titulo: "Personas y acceso", enlaces: ["Cuentas", "Participantes", "Registro asistido", "Piloto"] },
  { titulo: "Operación", enlaces: ["Recolectores", "Unidades", "Materiales", "Precios", "Educación"] },
  { titulo: "Seguimiento", enlaces: ["Conversaciones", "Reportes", "Liga de torres", "Actividad"] },
  { titulo: "Configuración", enlaces: ["Puntos", "Motivos", "Equivalencias", "Programa", "Sistema"] },
] as const;
type Seccion = (typeof gruposAdministracion)[number]["enlaces"][number];
/** Nombres claros en pantalla; el id interno de cada sección no cambia. */
const nombresVisibles: Partial<Record<string, string>> = {
  "Registro asistido": "Registrar vecino",
  Piloto: "Habilitación del piloto",
};
const nombreSeccion = (seccion: string) => nombresVisibles[seccion] ?? seccion;
/** Secciones con pantalla propia (AdminExtra.tsx), no la lista genérica. */
const seccionesPropias = new Set<string>(["Participantes", "Precios", "Conversaciones", "Reportes", "Liga de torres", "Actividad", "Programa"]);
const secciones = gruposAdministracion.map((grupo) => ({
  titulo: "titulo" in grupo ? grupo.titulo : undefined,
  enlaces: grupo.enlaces.map((seccion) => ({ id: seccion, texto: nombreSeccion(seccion) })),
}));
/** Cabecera de cada sección: ilustración 3D o icono, tono pastel y para qué sirve. */
const fichasSeccion: Record<Exclude<Seccion, "Inicio">, { imagen?: string; icono: string; tono: string; texto: string }> = {
  Cuentas: { imagen: "/panel/personas.webp", icono: "cuentas", tono: "verde", texto: "Quién entra al panel y con qué perfil: coordinación, recolectores, fundación y administración." },
  "Registro asistido": { icono: "registro asistido", tono: "turquesa", texto: "Inscribe a un vecino que no usa WhatsApp o llega en persona: con su consentimiento y vinculado a su unidad." },
  Piloto: { icono: "piloto", tono: "amarillo", texto: "El piloto es una prueba controlada: solo los vecinos habilitados, en su unidad y durante unas fechas, pueden pedir recolección." },
  Recolectores: { icono: "recolectores", tono: "verde", texto: "Huerteros y recicladores de cada colectivo que reciben las asignaciones." },
  Unidades: { icono: "unidades", tono: "lila", texto: "Hogares y negocios del conjunto que pueden pedir recolección." },
  Educación: { icono: "educación", tono: "amarillo", texto: "Guías de separación que los vecinos ven sin iniciar sesión." },
  Materiales: { imagen: "/panel/reciclaje.webp", icono: "materiales", tono: "lila", texto: "Tipos de material que se reciben y el colectivo que los atiende." },
  Puntos: { imagen: "/panel/estrella.webp", icono: "puntos", tono: "verde", texto: "Cuántos puntos gana la comunidad por cada entrega. Cada cambio crea una versión nueva." },
  Motivos: { icono: "motivos", tono: "turquesa", texto: "Razones para rechazar una entrega. Se desactivan, nunca se borran." },
  Equivalencias: { imagen: "/panel/monedas.webp", icono: "equivalencias", tono: "amarillo", texto: "Cuántos kilos equivalen a un balde o un bulto, para valorar cada entrega." },
  Sistema: { icono: "sistema", tono: "verde", texto: "Estado del servidor y de los servicios que usa el panel." },
  Participantes: { imagen: "/panel/personas.webp", icono: "participantes", tono: "lila", texto: "Los vecinos y negocios registrados, su unidad y si ya están habilitados en el piloto." },
  Precios: { imagen: "/panel/monedas.webp", icono: "precios", tono: "amarillo", texto: "Cuánto vale un kilo de cada material. Sirve para estimar el valor de lo aprovechado." },
  Conversaciones: { imagen: "/panel/vecina.webp", icono: "conversaciones", tono: "verde", texto: "Lo que cada vecino habló con Brisa por WhatsApp, como en el celular." },
  Reportes: { icono: "reportes", tono: "turquesa", texto: "Indicadores del programa y descargas en CSV para Excel." },
  "Liga de torres": { imagen: "/panel/estrella.webp", icono: "liga de torres", tono: "amarillo", texto: "Qué torre participa más: hogares con entregas válidas sobre el total de viviendas." },
  Actividad: { icono: "actividad", tono: "lila", texto: "Quién hizo qué y cuándo: la trazabilidad de solicitudes, cuentas, pesajes y cambios." },
  Programa: { icono: "programa", tono: "verde", texto: "Nombre, horarios, contacto y el saludo con el que Brisa recibe a los vecinos." },
};
const titulosFormulario: Partial<Record<string, string>> = {
  Cuentas: "Crear cuenta",
  Recolectores: "Agregar recolector",
  Unidades: "Crear unidad productiva",
  Piloto: "Habilitar participante",
  Puntos: "Nueva versión de regla",
  Educación: "Nuevo contenido",
  Materiales: "Agregar material",
  Motivos: "Agregar motivo",
  Equivalencias: "Nueva equivalencia",
};
const estadosOk = new Set(["Activo", "Vigente", "Publicado"]);
const estadosAlerta = new Set(["Vencida", "Borrador", "Aún no vigente", "Vínculo sin verificar", "Sin vínculo vigente", "Fuera de vigencia"]);
const estadosApagados = new Set(["Inactivo", "Inactiva", "Retirado"]);
function iniciales(texto: string) {
  return texto.split(/\s+/).filter((p) => /^[\p{L}\p{N}]/u.test(p)).slice(0, 2).map((p) => p[0]).join("").toUpperCase() || "·";
}

const rutas: Partial<Record<Seccion, string>> = {
  Cuentas: "cuentas-operadoras?limit=100",
  Recolectores: "recolectores?limit=100",
  Unidades: "unidades/gestion?limit=100&incluir_inactivas=true",
  Piloto: "piloto/habilitaciones",
  Puntos: "configuracion?tipo=reglas_incentivo",
  Educación: "contenidos-educativos/gestion?limit=100",
  Materiales: "materiales?limit=100",
  Motivos: "motivos-rechazo?limit=100",
  Equivalencias: "configuracion?tipo=equivalencias",
};
/* "Eliminar" never deletes: records are deactivated so orders, weighings and points keep their history
   (docs/diseno-base-de-datos.md). Each entry builds the PATCH that switches a row on or off. */
type CambioEstado = (fila: Fila, activo: boolean) => { ruta: string; cuerpo: unknown } | null;
const cambiosEstado: Partial<Record<Seccion, CambioEstado>> = {
  Cuentas: (f, activo) => ({ ruta: "cuentas-operadoras/" + f.id, cuerpo: { version_esperada: f.version, activo } }),
  Recolectores: (f, activo) => ({
    ruta: (f.tipo === "huertero" ? "huerteros/" : "recicladores/") + f.id,
    cuerpo: { version_esperada: f.version, activo },
  }),
  Unidades: (f, activo) => ({ ruta: "unidades/" + f.id, cuerpo: { activo } }),
  Educación: (f, activo) => ({ ruta: "contenidos-educativos/" + f.id, cuerpo: { version_esperada: f.version, activo } }),
  Materiales: (f, activo) => ({ ruta: "materiales/" + f.id, cuerpo: { version_esperada: f.version, activo } }),
  Motivos: (f, activo) => ({ ruta: "motivos-rechazo/" + f.id, cuerpo: { activo } }),
  // A revoked pilot enablement cannot be restored; a new one is created instead.
  Piloto: (f, activo) => (activo ? null : {
    ruta: "piloto/habilitaciones/" + f.id,
    cuerpo: { version_esperada: f.version, activo: false },
  }),
};
const textoBaja: Partial<Record<Seccion, string>> = { Piloto: "Revocar", Educación: "Retirar" };
const estadosActivo: [string, string][] = [["true", "Activo"], ["false", "Inactivo"]];
interface Capacidades {
  version_contrato: string;
  avisos: { modo: string };
  registro: { politica_datos_version: string };
}
export default function Administracion({ cuenta: cuentaSesion }: { cuenta: CuentaPanel }) {
  const [cuentaActiva, setCuentaActiva] = useState(false);
  const [vista, setVista] = useState<Seccion>("Inicio");
  const [seleccion, setSeleccion] = useState<Fila | null>(null);
  const [conflicto, setConflicto] = useState(false);
  const [aviso, setAviso] = useState<{ tipo: "exito" | "error"; texto: string } | null>(null);
  const [rol, setRol] = useState("");
  const [participanteId, setParticipanteId] = useState("");
  const [busqueda, setBusqueda] = useState("");
  const [formularioAbierto, setFormularioAbierto] = useState(false);
  const [modoLista, setModoLista] = useState<"tarjetas" | "tabla">(() => {
    try { return localStorage.getItem("brota.admin.modoLista") === "tabla" ? "tabla" : "tarjetas"; } catch { return "tarjetas"; }
  });
  const [orden, setOrden] = useState<{ col: "nombre" | "estado"; dir: 1 | -1 } | null>(null);
  function cambiarModo(m: "tarjetas" | "tabla") {
    setModoLista(m);
    try { localStorage.setItem("brota.admin.modoLista", m); } catch { /* sin almacenamiento */ }
  }
  function ordenarPor(col: "nombre" | "estado") {
    setOrden((o) => (o?.col === col ? { col, dir: o.dir === 1 ? -1 : 1 } : { col, dir: 1 }));
  }
  function cerrarFormulario() {
    setSeleccion(null);
    setFormularioAbierto(false);
  }
  const participantes = useDatos<ParticipantePiloto[]>(
    vista === "Piloto" ? "/v1/participantes" : "",
  );
  const participante = participantes.datos?.find((p) => p.id === participanteId);
  const rutaTrabajadores =
    vista !== "Cuentas" || seleccion
      ? ""
      : rol === "huertero"
        ? "/v1/huerteros?activo=true"
        : rol === "reciclador"
          ? "/v1/recicladores?activo=true"
          : "";
  const trabajadores = useDatos<Recolector[]>(rutaTrabajadores);
  const cat = useDatos<Catalogo & { materiales: ItemCatalogo[] }>(
    "/v1/catalogos",
  );
  const cap = useDatos<Capacidades>("/v1/capacidades");
  // Campana de administración: lo que conviene revisar sin entrar a cada sección.
  const habilitaciones = useDatos<Fila[]>("/v1/piloto/habilitaciones");
  const contenidos = useDatos<Fila[]>("/v1/contenidos-educativos/gestion?limit=100");
  const avisosAdmin: AvisoPanel[] = [];
  {
    const ahora = Date.now();
    const semana = 7 * 24 * 3600 * 1000;
    const activas = (habilitaciones.datos ?? []).filter((h) => h.activo && h.vigente_hasta);
    const vencidas = activas.filter((h) => Date.parse(h.vigente_hasta!) <= ahora).length;
    const porVencer = activas.filter((h) => {
      const fin = Date.parse(h.vigente_hasta!);
      return fin > ahora && fin - ahora <= semana;
    }).length;
    const borradores = (contenidos.datos ?? []).filter((c) => c.activo !== false && c.publicado === false).length;
    if (vencidas) avisosAdmin.push({ id: "piloto-vencidas", destino: "Piloto", icono: "piloto",
      texto: `${vencidas} habilitación${vencidas === 1 ? "" : "es"} del piloto vencida${vencidas === 1 ? "" : "s"}` });
    if (porVencer) avisosAdmin.push({ id: "piloto-vence", destino: "Piloto", icono: "piloto",
      texto: `${porVencer} habilitación${porVencer === 1 ? "" : "es"} vence${porVencer === 1 ? "" : "n"} esta semana` });
    if (borradores) avisosAdmin.push({ id: "educacion-borradores", destino: "Educación", icono: "educación",
      texto: `${borradores} contenido${borradores === 1 ? "" : "s"} educativo${borradores === 1 ? "" : "s"} sin publicar` });
  }
  const lista = useDatos<Fila[]>(rutas[vista] ? "/v1/" + rutas[vista] : "");
  const vinculados = new Set(
    vista === "Cuentas" ? lista.datos?.map((fila) => fila.trabajador_id) : [],
  );
  const trabajadoresDisponibles = lista.datos && trabajadores.datos?.filter(
    (trabajador) => !vinculados.has(trabajador.id),
  );
  const unidades = useDatos<Fila[]>(
    vista === "Registro asistido" ? "/v1/unidades/gestion?limit=100" : "",
  );
  const opciones = (items: ItemCatalogo[] = []): [string, string][] =>
    items.map((i) => [i.id, i.nombre]);
  const gremio = (
    <Campo
      nombre="gremio_id"
      titulo="Colectivo"
      opciones={opciones(cat.datos?.gremios)}
    />
  );
  const nombre = <Campo nombre="nombre" titulo="Nombre" maxLength={120} />;
  const codigo = (
    <Campo
      nombre="codigo"
      titulo="Código (mayúsculas, números o guion bajo)"
      pattern="[A-Z0-9_]+"
      maxLength={40}
    />
  );
  const cuenta = seleccion;
  function preparar(v: Valores): Operacion {
    switch (vista) {
      case "Cuentas": {
        if (cuenta) {
          return {
            metodo: "PATCH",
            ruta: "cuentas-operadoras/" + cuenta.id,
            cuerpo: {
              version_esperada: cuenta.version,
              ...(v.pin ? { pin: v.pin } : {}),
              activo: v.activo === "true",
            },
          };
        }
        const esTrabajador = v.rol === "huertero" || v.rol === "reciclador";
        const trabajador = esTrabajador && v.rol === rol
          ? trabajadoresDisponibles?.find((item) => item.id === v.trabajador_id)
          : undefined;
        if (esTrabajador && !trabajador)
          throw Error("Selecciona un trabajador activo del perfil elegido.");
        return {
          ruta: "cuentas-operadoras",
          cuerpo: {
            nombre: v.nombre,
            usuario: v.usuario,
            pin: v.pin,
            ...(trabajador ? { trabajador_id: trabajador.id } : {}),
            permisos: [
              {
                rol: v.rol,
                gremio_id: trabajador?.gremio_id ?? (v.rol === "coordinacion" ? v.gremio_id : null),
              },
            ],
          },
        };
      }
      case "Recolectores":
        if (seleccion) {
          return {
            metodo: "PATCH",
            ruta: (seleccion.tipo === "huertero" ? "huerteros/" : "recicladores/") + seleccion.id,
            cuerpo: {
              version_esperada: seleccion.version,
              nombre: v.nombre,
              telefono_contacto: v.telefono_contacto || null,
              activo: v.activo === "true",
            },
          };
        }
        return {
          ruta: "recolectores",
          cuerpo: { ...v, telefono_contacto: v.telefono_contacto || null },
        };
      case "Unidades":
        return { ruta: "unidades", cuerpo: { tipo: "negocio", ...v } };
      case "Registro asistido":
        if (!cap.datos)
          throw Error("Espera a que cargue la política de datos.");
        return {
          ruta: "registros/asistidos",
          cuerpo: {
            nombre: v.nombre,
            unidad_id: v.unidad_id,
            consentimiento: {
              decision: "aceptado",
              version_politica: cap.datos!.registro.politica_datos_version,
            },
          },
        };
      case "Piloto": {
        if (seleccion) {
          const revocar = v.accion_piloto === "revocar";
          const quitarFin = v.accion_piloto === "quitar_fin";
          const fechaActual = seleccion.vigente_hasta
            ? fechaBogota(new Date(seleccion.vigente_hasta))
            : "";
          if (v.accion_piloto === "vigencia" && !v.hasta)
            throw Error("Indica la nueva fecha de fin o elige quitar el vencimiento.");
          return {
            metodo: "PATCH",
            ruta: "piloto/habilitaciones/" + seleccion.id,
            cuerpo: {
              version_esperada: seleccion.version,
              activo: !revocar && seleccion.activo === true,
              ...(quitarFin ? { vigente_hasta: null } : {}),
              ...(v.accion_piloto === "vigencia" && v.hasta !== fechaActual
                ? { vigente_hasta: inicioDiaBogota(v.hasta) }
                : {}),
            },
          };
        }
        if (!participante || v.participante_id !== participante.id ||
            !participante.unidades.some((unidad) => unidad.id === v.unidad_id))
          throw Error("Selecciona un participante y una de sus unidades vigentes.");
        return {
          ruta: "piloto/habilitaciones",
          cuerpo: {
            participante_id: v.participante_id,
            unidad_id: v.unidad_id,
            vigente_desde: inicioDiaBogota(v.desde),
            vigente_hasta: inicioDiaBogota(v.hasta),
          },
        };
      }
      case "Puntos":
        return {
          ruta: "reglas-incentivo",
          cuerpo: {
            codigo: v.codigo,
            modalidad: "entrega_valida",
            ambito: { tipo: "gremio", id: v.gremio_id },
            parametros: { puntos: Number(v.puntos) },
          },
        };
      case "Educación":
        if (seleccion) {
          if (v.accion_contenido === "publicar" && seleccion.activo === false)
            throw Error("Reactiva el contenido antes de publicarlo.");
          if (!["guardar", "publicar", "retirar", "reactivar"].includes(v.accion_contenido))
            throw Error("Selecciona una acción.");
          return {
            metodo: "PATCH",
            ruta: "contenidos-educativos/" + seleccion.id,
            cuerpo: {
              version_esperada: seleccion.version,
              titulo: v.titulo,
              texto: v.texto,
              tema: v.tema,
              ...(v.accion_contenido === "publicar" ? { publicado: true } : {}),
              ...(v.accion_contenido === "retirar" ? { activo: false } : {}),
              ...(v.accion_contenido === "reactivar" ? { activo: true } : {}),
            },
          };
        }
        return {
          ruta: "contenidos-educativos",
          cuerpo: {
            titulo: v.titulo,
            texto: v.texto,
            tema: v.tema,
            publicado: v.publicado === "true",
            general: false,
            tipo: "texto",
          },
        };
      case "Materiales":
        if (seleccion) {
          return {
            metodo: "PATCH",
            ruta: "materiales/" + seleccion.id,
            cuerpo: {
              version_esperada: seleccion.version,
              nombre: v.nombre,
              activo: v.activo === "true",
            },
          };
        }
        return { ruta: "materiales", cuerpo: v };
      case "Motivos":
        return { ruta: "motivos-rechazo", cuerpo: v };
      case "Equivalencias":
        return { ruta: "equivalencias", cuerpo: v };
      default:
        throw Error("Selecciona una operación.");
    }
  }
  const filas: Fila[] | undefined = lista.datos;
  async function cambiarEstado(fila: Fila, activo: boolean) {
    const cambio = cambiosEstado[vista]?.(fila, activo);
    if (!cambio) return;
    setAviso(null);
    try {
      await pedir("PATCH", "/v1/" + cambio.ruta, { cuerpo: cambio.cuerpo, clave: claveNueva() });
      setAviso({ tipo: "exito", texto: activo ? "Registro reactivado." : "Registro desactivado. Su historial se conserva." });
      if (seleccion?.id === fila.id) setSeleccion(null);
      lista.recargar();
      cat.recargar();
    } catch (e) {
      setAviso({ tipo: "error", texto: (e as Error).message });
    }
  }
  function navegar(id: string) {
    setCuentaActiva(id === enlaceCuenta.id);
    if (id === enlaceCuenta.id || !gruposAdministracion.some((grupo) => grupo.enlaces.some((item) => item === id))) return;
    setVista(id as Seccion);
    setSeleccion(null);
    setConflicto(false);
    setAviso(null);
    setRol("");
    setParticipanteId("");
    setBusqueda("");
    setFormularioAbierto(false);
    setOrden(null);
  }

  const tituloFormulario: string =
                seleccion && vista === "Educación"
                  ? seleccion.titulo || "Contenido educativo"
                  : seleccion && vista === "Piloto"
                  ? "Cambiar habilitación"
                  : seleccion && vista === "Recolectores"
                  ? "Editar " + (seleccion.nombre || "recolector")
                  : seleccion && vista === "Materiales"
                  ? "Editar " + (seleccion.nombre || "material")
                  : cuenta && vista === "Cuentas"
                  ? "Acceso de " + cuenta.nombre
                  : ({
                      Cuentas: "Crear cuenta",
                      Recolectores: "Agregar recolector",
                      Unidades: "Crear unidad productiva",
                      "Registro asistido": "Registrar participante",
                      Piloto: "Habilitar participante",
                      Puntos: "Nueva versión de regla",
                      Educación: "Editor de contenido educativo",
                      Materiales: "Agregar material",
                      Motivos: "Agregar motivo",
                      Equivalencias: "Nueva equivalencia",
                    } as Partial<Record<string, string>>)[vista] ?? "Formulario";

  return (
    <MarcoPanel grupos={secciones} activo={cuentaActiva ? enlaceCuenta.id : vista}
      titulo={cuentaActiva ? enlaceCuenta.texto : vista === "Inicio" ? "Administración" : nombreSeccion(vista)}
      contexto="Administración de EcoConecta" cuenta={cuentaSesion} navegar={navegar} avisos={avisosAdmin}
      portada={!cuentaActiva}>
      {vista !== "Inicio" && (
        <CabeceraSeccion vista={vista}
          cantidad={rutas[vista] ? filas?.length : undefined}
          busqueda={rutas[vista] ? busqueda : undefined} alBuscar={setBusqueda}
          nuevo={rutas[vista] && titulosFormulario[vista]
            ? { texto: titulosFormulario[vista]!, onClick: () => { setSeleccion(null); setAviso(null); setFormularioAbierto(true); } }
            : undefined} />
      )}
      {conflicto && (
        <p className="aviso aviso-error" role="alert">Este registro cambió. Vuelve a seleccionarlo para revisar la versión actual.</p>
      )}
      {vista === "Sistema" ? (
        <section className="eco-tarjeta">
          <h2>Estado del sistema</h2>
          {cap.datos ? (
            <ul className="sistema-estado">
              <li><span className="registro-avatar tono-verde"><Icono nombre="sistema" /></span>
                <span><small>Versión del contrato</small><strong>{cap.datos.version_contrato}</strong></span>
                <span className="registro-estado estado-ok"><Icono nombre="check" />En línea</span></li>
              <li><span className="registro-avatar tono-lila"><Icono nombre="campana" /></span>
                <span><small>Avisos a vecinos</small><strong>Modo {cap.datos.avisos.modo}</strong></span>
                <span className="registro-estado estado-ok"><Icono nombre="check" />Activo</span></li>
              <li><span className="registro-avatar tono-amarillo"><Icono nombre="hoja" /></span>
                <span><small>IA en este panel</small><strong>Desactivada</strong></span>
                <span className="registro-estado estado-apagado">La IA vive en Brisa</span></li>
            </ul>
          ) : (
            <Espera error={cap.error} reintentar={cap.recargar} />
          )}
        </section>
      ) : seccionesPropias.has(vista) ? (
        vista === "Participantes" ? <Participantes navegar={navegar} />
          : vista === "Precios" ? <Precios />
          : vista === "Conversaciones" ? <Conversaciones />
          : vista === "Reportes" ? <Reportes />
          : vista === "Liga de torres" ? <LigaTorres />
          : vista === "Actividad" ? <Actividad />
          : <Programa />
      ) : vista === "Inicio" ? (
        <Portada saludo={`¡Hola, ${cuentaSesion.nombre.trim().split(/\s+/)[0] || cuentaSesion.nombre}!`}
          texto="Aquí puedes configurar la información general de Brota." imagen="/panel/vecina.webp">
          <TarjetaAccion icono="cuentas" imagen="/panel/personas.webp" titulo="Usuarios"
            texto="Gestiona las personas que usan la plataforma." onClick={() => navegar("Cuentas")} />
          <TarjetaAccion icono="materiales" imagen="/panel/reciclaje.webp" titulo="Materiales" tono="lila"
            texto="Define los tipos de material que se reciben." onClick={() => navegar("Materiales")} />
          <TarjetaAccion icono="equivalencias" imagen="/panel/monedas.webp" titulo="Equivalencias" tono="amarillo"
            texto="Convierte baldes y bultos en kilos para valorar cada entrega." onClick={() => navegar("Equivalencias")} />
          <TarjetaAccion icono="puntos" imagen="/panel/estrella.webp" titulo="Reglas de puntos"
            texto="Establece cómo se otorgan los puntos a la comunidad." onClick={() => navegar("Puntos")} />
        </Portada>
      ) : null}
      {vista === "Inicio" && !cuentaActiva ? (
        <TableroInicio navegar={navegar} />
      ) : vista === "Inicio" || vista === "Sistema" || seccionesPropias.has(vista) ? null
      : vista === "Piloto" && !lista.datos ? (
        <section className="eco-tarjeta">
          <h2>Habilitaciones del piloto</h2>
          <p>
            El permiso se asigna por persona y unidad, con vigencia. La gestión
            requiere el módulo de piloto del servidor.
          </p>
          <Espera error={lista.error} reintentar={lista.recargar} />
        </section>
      ) : (
        <div className="row g-3">
          <div className={vista === "Registro asistido" ? "col-12 col-lg-6" : "col-12"}>
            <section className="eco-tarjeta">
              <div className="lista-encabezado">
                <h2>{nombreSeccion(vista)}</h2>
                {rutas[vista] && (
                  <div className="lista-modo" role="group" aria-label="Ver la lista como">
                    <button type="button" aria-pressed={modoLista === "tarjetas"} onClick={() => cambiarModo("tarjetas")}>
                      <Icono nombre="tarjetas" />Tarjetas
                    </button>
                    <button type="button" aria-pressed={modoLista === "tabla"} onClick={() => cambiarModo("tabla")}>
                      <Icono nombre="tabla" />Tabla
                    </button>
                  </div>
                )}
              </div>
              {aviso && <Estado tipo={aviso.tipo}>{aviso.texto}</Estado>}
              {vista === "Piloto" && !participantes.datos && (
                <Espera error={participantes.error} reintentar={participantes.recargar} />
              )}
              {vista === "Registro asistido" ? (
                <p>
                  Registra a la persona con su consentimiento y vincúlala a la
                  unidad. La habilitación del piloto es un paso independiente.
                </p>
              ) : !filas ? (
                <Espera
                  error={lista.error || cat.error}
                  reintentar={() => {
                    lista.recargar();
                    cat.recargar();
                  }}
                />
              ) : filas.length === 0 ? (
                <div className="vacio-clay">
                  <img src="/panel/reciclaje.webp" alt="" />
                  <p>Todavía no hay registros. Crea el primero con el formulario.</p>
                </div>
              ) : (() => {
                const filasVista = [...filas].map((f) => {
                  const persona = vista === "Piloto"
                    ? participantes.datos?.find((p) => p.id === f.participante_id)
                    : undefined;
                  const unidad = persona?.unidades.find((u) => u.id === f.unidad_id);
                  const titulo = (vista === "Unidades" && (f.etiqueta || f.referencia_local)) ||
                    persona?.nombre || f.nombre || f.titulo || f.referencia_local || f.codigo ||
                    f.recipiente || f.estado || "Habilitación";
                  const datos = [
                    vista === "Piloto" && participantes.datos &&
                      (unidad?.etiqueta || "Unidad sin vínculo vigente"),
                    vista === "Unidades" && (f.tipo === "negocio" ? "Negocio" : f.tipo === "hogar" ? "Hogar" : ""),
                    f.tipo === "huertero" ? "Huertero" : f.tipo === "reciclador" ? "Reciclador" : "",
                    f.telefono_contacto,
                    f.codigo && f.nombre ? f.codigo : "",
                    f.tema && temasEducativos[f.tema],
                    f.usuario,
                    f.permisos?.map((p) => p.rol).join(", "),
                    vista === "Educación"
                      ? estadoContenido(f)
                      : vista === "Piloto"
                      ? estadoPiloto(f, participantes.datos ? Boolean(unidad) : undefined)
                      : f.activo === undefined
                      ? ""
                      : f.activo
                        ? "Activo"
                        : "Inactivo",
                    f.parametros?.puntos !== undefined ? f.parametros.puntos + " puntos" : "",
                    f.kg_por_unidad ? f.kg_por_unidad + " kg/unidad" : "",
                    f.vigente_desde && "Desde " + fechaBogota(new Date(f.vigente_desde)),
                    f.vigente_hasta && "Vence " + fechaBogota(new Date(f.vigente_hasta)),
                  ].filter((d): d is string => Boolean(d));
                  return { f, titulo, datos };
                });
                const consulta = busqueda.trim().toLocaleLowerCase("es");
                const visibles = consulta
                  ? [...filasVista].filter(({ f, titulo, datos }) =>
                    [titulo, ...datos, f.texto ?? ""].join(" ").toLocaleLowerCase("es").includes(consulta))
                  : [...filasVista];
                const estadoDe = (datos: string[]) =>
                  datos.find((d) => estadosOk.has(d) || estadosAlerta.has(d) || estadosApagados.has(d)) ?? "";
                if (orden) {
                  const clave = (x: (typeof visibles)[number]) => (orden.col === "nombre" ? x.titulo : estadoDe(x.datos));
                  visibles.sort((a, b) => orden.dir * clave(a).localeCompare(clave(b), "es", { numeric: true }));
                }
                const conPersona = vista === "Cuentas" || vista === "Recolectores" || vista === "Piloto";
                const ficha = fichasSeccion[vista as Exclude<Seccion, "Inicio">];
                if (visibles.length === 0)
                  return <div className="vacio-clay"><p>Nada coincide con «{busqueda.trim()}».</p></div>;
                const accionesFila = (f: Fila) => {
                  const cambio = cambiosEstado[vista];
                  const propia = vista === "Cuentas" && f.nombre === cuentaSesion.nombre;
                  return (
                    <div className="registro-acciones">
                      {(vista === "Piloto" || vista === "Educación" || vista === "Recolectores" ||
                        vista === "Materiales" || vista === "Cuentas") && (
                        <button className="btn btn-sm registro-editar"
                          onClick={() => { setConflicto(false); setAviso(null); setSeleccion(f); setFormularioAbierto(true); }}>
                          <Icono nombre={vista === "Cuentas" ? "llave" : "editar"} />
                          {vista === "Piloto" ? "Cambiar" : vista === "Cuentas" ? "Acceso" : "Editar"}
                        </button>
                      )}
                      {cambio && !propia && (f.activo === false
                        ? cambio(f, true) && (
                          <button className="btn btn-sm exito" onClick={() => cambiarEstado(f, true)}>Reactivar</button>
                        )
                        : <BotonBaja texto={textoBaja[vista] ?? "Eliminar"} alConfirmar={() => cambiarEstado(f, false)} />)}
                    </div>
                  );
                };
                const flecha = (col: "nombre" | "estado") => (orden?.col === col ? (orden.dir === 1 ? " ▲" : " ▼") : "");
                if (modoLista === "tabla")
                  return (
                    <Paginada key={vista + "|" + consulta + "|" + (orden ? orden.col + orden.dir : "")} items={visibles} porPagina={10} etiqueta={nombreSeccion(vista)}>
                      {(pagina) => (
                        <div className="tabla-envoltura">
                          <table className="tabla-clay">
                            <thead>
                              <tr>
                                <th aria-sort={orden?.col === "nombre" ? (orden.dir === 1 ? "ascending" : "descending") : undefined}>
                                  <button type="button" className="tabla-orden" onClick={() => ordenarPor("nombre")}>Nombre{flecha("nombre")}</button>
                                </th>
                                <th>Detalles</th>
                                <th aria-sort={orden?.col === "estado" ? (orden.dir === 1 ? "ascending" : "descending") : undefined}>
                                  <button type="button" className="tabla-orden" onClick={() => ordenarPor("estado")}>Estado{flecha("estado")}</button>
                                </th>
                                <th><span className="visually-hidden">Acciones</span></th>
                              </tr>
                            </thead>
                            <tbody>
                              {pagina.map(({ f, titulo, datos }, n) => {
                                const estado = estadoDe(datos);
                                return (
                                  <tr key={f.id} className={f.activo === false ? "registro-inactivo" : undefined}
                                    style={{ "--n": Math.min(n, 12) } as CSSProperties}>
                                    <td>
                                      <span className="celda-persona">
                                        <span className={"registro-avatar tono-" + ficha.tono} aria-hidden="true">
                                          {conPersona ? iniciales(titulo) : <Icono nombre={ficha.icono} />}
                                        </span>
                                        <strong>{titulo}</strong>
                                      </span>
                                    </td>
                                    <td><span className="registro-datos">{datos.filter((d) => d !== estado).map((d, i) => (
                                      <span key={i} className="registro-dato">{d}</span>))}</span></td>
                                    <td>{estado && (
                                      <span className={"registro-estado " + (estadosOk.has(estado) ? "estado-ok" : estadosAlerta.has(estado) ? "estado-alerta" : "estado-apagado")}>
                                        <Icono nombre={estadosOk.has(estado) ? "check" : estadosAlerta.has(estado) ? "reloj" : "cerrar"} />{estado}
                                      </span>)}</td>
                                    <td className="celda-acciones">{accionesFila(f)}</td>
                                  </tr>
                                );
                              })}
                            </tbody>
                          </table>
                        </div>
                      )}
                    </Paginada>
                  );
                return (
                <Paginada key={vista + "|" + consulta + "|" + (orden ? orden.col + orden.dir : "")} items={visibles} porPagina={6} etiqueta={nombreSeccion(vista)}>
                {(pagina) => (
                <ul className="registros registros-clay">
                  {pagina.map(({ f, titulo, datos }, n) => {
                    return (
                    <li key={f.id} className={f.activo === false ? "registro-inactivo" : undefined}
                      style={{ "--n": Math.min(n, 12) } as CSSProperties}>
                      <span className={"registro-avatar tono-" + ficha.tono} aria-hidden="true">
                        {conPersona ? iniciales(titulo) : <Icono nombre={ficha.icono} />}
                      </span>
                      <div className="registro-texto">
                        <strong>{titulo}</strong>
                        <div className="registro-datos">
                          {datos.map((d, i) => (
                            <span key={i} className={
                              estadosOk.has(d) ? "registro-estado estado-ok"
                                : estadosAlerta.has(d) ? "registro-estado estado-alerta"
                                : estadosApagados.has(d) ? "registro-estado estado-apagado"
                                : "registro-dato"}>
                              {(estadosOk.has(d) || estadosAlerta.has(d) || estadosApagados.has(d)) && (
                                <Icono nombre={estadosOk.has(d) ? "check" : estadosAlerta.has(d) ? "reloj" : "cerrar"} />
                              )}
                              {d}
                            </span>
                          ))}
                        </div>
                        {f.texto && <p className="registro-descripcion">{f.texto}</p>}
                      </div>
                      {accionesFila(f)}
                    </li>
                    );
                  })}
                </ul>
                )}
                </Paginada>
                );
              })()}
            </section>
          </div>
          {(() => {
          const formulario = (
            <Formulario
              key={vista + (cuenta?.id || "")}
              preparar={preparar}
              alConflicto={() => {
                setConflicto(true);
                setSeleccion(null);
                lista.recargar();
              }}
              accion="Guardar"
              alVolver={seleccion ? cerrarFormulario : undefined}
              titulo={tituloFormulario}
              alGuardar={() => {
                setFormularioAbierto(false);
                if (vista === "Cuentas" && !cuenta) setRol("");
                if (vista === "Piloto") setParticipanteId("");
                setSeleccion(null);
                lista.recargar();
                cat.recargar();
              }}
            >
              {vista === "Cuentas" &&
                (cuenta ? (
                  <>
                    <Pildoras nombre="activo" titulo="Estado" opciones={estadosActivo}
                      valorInicial={String(cuenta.activo)} />
                    <Campo
                      nombre="pin"
                      titulo="Nuevo PIN (opcional)"
                      tipo="password"
                      opcional
                      pattern="[0-9]{4,12}"
                    />
                  </>
                ) : (
                  <>
                    {nombre}
                    <Campo
                      nombre="usuario"
                      titulo="Usuario"
                      pattern="[a-zA-Z0-9._\\-]{3,60}"
                    />
                    <Campo
                      nombre="pin"
                      titulo="PIN de 4 a 12 dígitos"
                      tipo="password"
                      pattern="[0-9]{4,12}"
                    />
                    <label>
                      Perfil
                      <select
                        name="rol"
                        required
                        value={rol}
                        onChange={(e) => setRol(e.target.value)}
                      >
                        <option value="" disabled hidden>Selecciona un perfil</option>
                        <option value="coordinacion">Coordinación</option>
                        <option value="huertero">Huertero</option>
                        <option value="reciclador">Reciclador</option>
                        <option value="fundacion">Fundación</option>
                        <option value="admin">Administración</option>
                      </select>
                    </label>
                    {rol === "coordinacion" && gremio}
                    {rutaTrabajadores && (
                      <>
                        <Campo
                          key={rol}
                          nombre="trabajador_id"
                          titulo={rol === "huertero" ? "Huertero" : "Reciclador"}
                          opciones={trabajadoresDisponibles?.map(({ id, nombre }) => [id, nombre]) ?? []}
                        />
                        {!trabajadores.datos ? (
                          <Espera error={trabajadores.error} reintentar={trabajadores.recargar} />
                        ) : trabajadoresDisponibles?.length === 0 && (
                          <p role="status">No hay trabajadores activos sin cuenta para este perfil.</p>
                        )}
                      </>
                    )}
                  </>
                ))}
              {vista === "Recolectores" && (
                seleccion ? (
                  <>
                    <Campo nombre="nombre" titulo="Nombre" maxLength={120} valorInicial={seleccion.nombre} />
                    <Campo
                      nombre="telefono_contacto"
                      titulo="Teléfono de contacto (opcional)"
                      tipo="tel"
                      opcional
                      valorInicial={seleccion.telefono_contacto ?? ""}
                    />
                    <Pildoras nombre="activo" titulo="Estado" opciones={estadosActivo}
                      valorInicial={String(seleccion.activo)} />
                  </>
                ) : (
                  <>
                    {nombre}
                    {gremio}
                    <Campo
                      nombre="telefono_contacto"
                      titulo="Teléfono de contacto (opcional)"
                      tipo="tel"
                      opcional
                    />
                  </>
                )
              )}
              {vista === "Unidades" && (
                <>
                  <Campo
                    nombre="referencia_local"
                    titulo="Nombre del negocio"
                    maxLength={60}
                  />
                  <Campo
                    nombre="direccion_referencia"
                    titulo="Dirección o referencia operativa"
                    maxLength={200}
                  />
                </>
              )}
              {vista === "Registro asistido" && (
                <>
                  {nombre}
                  <Campo
                    nombre="unidad_id"
                    titulo="Unidad vinculada"
                    opciones={
                      unidades.datos?.map((u) => [
                        u.id,
                        u.etiqueta || u.referencia_local || u.id,
                      ]) || []
                    }
                  />
                  {unidades.error && <Espera error={unidades.error} reintentar={unidades.recargar} />}
                  {!cap.datos ? (
                    <Espera error={cap.error} reintentar={cap.recargar} />
                  ) : (
                    <label className="casilla">
                      <input type="checkbox" required />
                      <span>La persona autorizó registrar sus datos para coordinar las entregas.</span>
                    </label>
                  )}
                </>
              )}
              {vista === "Piloto" && (
                <>
                  {seleccion ? (
                    <Campo nombre="accion_piloto" titulo="Acción" opciones={[
                      ["vigencia", "Cambiar fecha de fin"],
                      ...(seleccion.vigente_hasta ? [["quitar_fin", "Quitar vencimiento"] as [string, string]] : []),
                      ...(seleccion.activo ? [["revocar", "Revocar habilitación"] as [string, string]] : []),
                    ]} />
                  ) : (
                    <>
                      <label>
                        Participante
                        <select name="participante_id" required value={participanteId} onChange={(e) => setParticipanteId(e.target.value)}>
                          <option value="" disabled hidden>Selecciona un participante</option>
                          {participantes.datos?.filter((p) => p.unidades.length > 0).map((p) => (
                            <option key={p.id} value={p.id}>{p.nombre}</option>
                          ))}
                        </select>
                      </label>
                      <Campo key={participanteId} nombre="unidad_id" titulo="Unidad vinculada" opciones={
                        participante?.unidades.map((u) => [u.id, u.etiqueta]) ?? []
                      } />
                      <Campo nombre="desde" titulo="Inicio de vigencia" tipo="date" />
                    </>
                  )}
                  <label>
                    Fin de vigencia al inicio de este día
                    <input
                      name="hasta"
                      type="date"
                      defaultValue={seleccion?.vigente_hasta
                        ? fechaBogota(new Date(seleccion.vigente_hasta))
                        : ""}
                    />
                  </label>
                </>
              )}
              {vista === "Puntos" && (
                <>
                  {codigo}
                  {gremio}
                  <Campo
                    nombre="puntos"
                    titulo="Puntos por entrega validada"
                    tipo="number"
                    min={0}
                  />
                  <p>
                    Propuesta del equipo, pendiente de validación de la
                    Fundación. Se aplica a entregas nuevas.
                  </p>
                </>
              )}
              {vista === "Educación" && (
                seleccion ? (
                  <>
                    <p>{estadoContenido(seleccion)}</p>
                    <Campo nombre="titulo" titulo="Título" maxLength={160} valorInicial={seleccion.titulo} />
                    <Campo
                      nombre="tema"
                      titulo="Tema"
                      valorInicial={seleccion.tema}
                      opciones={Object.entries(temasEducativos)}
                    />
                    <Campo
                      nombre="texto"
                      titulo="Contenido educativo"
                      tipo="textarea"
                      maxLength={2000}
                      valorInicial={seleccion.texto ?? ""}
                    />
                    <Campo
                      nombre="accion_contenido"
                      titulo="Acción"
                      valorInicial="guardar"
                      opciones={accionesContenido(seleccion)}
                    />
                  </>
                ) : <>
                  <Campo nombre="titulo" titulo="Título" maxLength={160} />
                  <Campo nombre="tema" titulo="Tema" opciones={
                    Object.entries(temasEducativos)
                  } />
                  <Campo
                    nombre="texto"
                    titulo="Contenido educativo"
                    tipo="textarea"
                    maxLength={2000}
                  />
                  <Campo nombre="publicado" titulo="Publicación" opciones={[
                    ["true", "Publicar en la guía"],
                    ["false", "Guardar como borrador"],
                  ]} />
                </>
              )}
              {vista === "Materiales" && (
                seleccion ? (
                  <>
                    <p>Código: {seleccion.codigo}. El código y el colectivo no cambian.</p>
                    <Campo nombre="nombre" titulo="Nombre" maxLength={120} valorInicial={seleccion.nombre} />
                    <Pildoras nombre="activo" titulo="Estado" opciones={estadosActivo}
                      valorInicial={String(seleccion.activo)} />
                  </>
                ) : (
                  <>
                    {nombre}
                    {codigo}
                    {gremio}
                  </>
                )
              )}
              {vista === "Motivos" && (
                <>
                  {nombre}
                  {codigo}
                  {gremio}
                </>
              )}
              {vista === "Equivalencias" && (
                <>
                  {gremio}
                  <Campo nombre="recipiente" titulo="Recipiente" />
                  <Campo
                    nombre="kg_por_unidad"
                    titulo="Kilos por unidad"
                    tipo="number"
                    min={0.001}
                    step="0.001"
                  />
                </>
              )}
            </Formulario>
          );
          if (vista === "Registro asistido") return <div className="col-12 col-lg-6">{formulario}</div>;
          if (!formularioAbierto && !seleccion) return null;
          return <Modal titulo={tituloFormulario} onCerrar={cerrarFormulario}>{formulario}</Modal>;
          })()}
        </div>
      )}
    </MarcoPanel>
  );
}


function CabeceraSeccion({ vista, cantidad, busqueda, alBuscar, nuevo }: {
  vista: Exclude<Seccion, "Inicio">;
  cantidad?: number;
  busqueda?: string;
  alBuscar: (texto: string) => void;
  nuevo?: { texto: string; onClick: () => void };
}) {
  const ficha = fichasSeccion[vista];
  return (
    <section className={"seccion-cabecera tono-" + ficha.tono}>
      {ficha.imagen
        ? <img className="seccion-cabecera-imagen" src={ficha.imagen} alt="" />
        : <span className="seccion-cabecera-icono" aria-hidden="true"><Icono nombre={ficha.icono} /></span>}
      <div className="seccion-cabecera-texto">
        <p className="seccion-cabecera-titulo">
          {nombreSeccion(vista)}
          {cantidad !== undefined && (
            <span className="seccion-cabecera-cantidad">{cantidad} registro{cantidad === 1 ? "" : "s"}</span>
          )}
        </p>
        <p>{ficha.texto}</p>
      </div>
      {busqueda !== undefined && (
        <label className="seccion-buscar">
          <Icono nombre="buscar" />
          <span className="visually-hidden">Buscar en {nombreSeccion(vista)}</span>
          <input type="search" value={busqueda} onChange={(e) => alBuscar(e.target.value)}
            placeholder={"Buscar en " + nombreSeccion(vista).toLowerCase()} />
        </label>
      )}
      {nuevo && (
        <button type="button" className="btn primario seccion-nuevo" onClick={nuevo.onClick}>
          <Icono nombre="nuevo" />{nuevo.texto}
        </button>
      )}
    </section>
  );
}
