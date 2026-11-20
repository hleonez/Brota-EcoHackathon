import { MarcoPanel, enlaceCuenta, type CuentaPanel } from "./MarcoPanel";
import { useState } from "react";
import { Campo, Formulario, type Operacion, type Valores } from "./Formulario";
import { Espera, fechaBogota, useDatos } from "./portal";
import { temasEducativos, type TemaEducativo } from "./temasEducativos";
import type { Catalogo, ItemCatalogo, Recolector } from "./tipos";

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
  return [
    ["guardar", "Guardar cambios"],
    ["publicar", "Publicar en la guía"],
    ["retirar", "Retirar de la guía"],
  ];
}
const gruposAdministracion = [
  { enlaces: ["Inicio"] },
  { titulo: "Personas y acceso", enlaces: ["Cuentas", "Registro asistido", "Piloto"] },
  { titulo: "Contenido y operación", enlaces: ["Recolectores", "Unidades", "Educación", "Materiales"] },
  { titulo: "Configuración", enlaces: ["Puntos", "Motivos", "Equivalencias", "Sistema"] },
] as const;
type Seccion = (typeof gruposAdministracion)[number]["enlaces"][number];
const secciones = gruposAdministracion.map((grupo) => ({
  titulo: "titulo" in grupo ? grupo.titulo : undefined,
  enlaces: grupo.enlaces.map((seccion) => ({ id: seccion, texto: seccion })),
}));
const rutas: Partial<Record<Seccion, string>> = {
  Cuentas: "cuentas-operadoras?limit=100",
  Recolectores: "recolectores?limit=100",
  Unidades: "unidades/gestion?limit=100",
  Piloto: "piloto/habilitaciones",
  Puntos: "configuracion?tipo=reglas_incentivo",
  Educación: "contenidos-educativos/gestion?limit=100",
  Materiales: "materiales?limit=100",
  Equivalencias: "configuracion?tipo=equivalencias",
};
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
  const [rol, setRol] = useState("");
  const [participanteId, setParticipanteId] = useState("");
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
  const filas: Fila[] | undefined =
    vista === "Motivos"
      ? cat.datos?.motivos_rechazo.map((m) => ({ ...m, version: 0 }))
      : lista.datos;
  function navegar(id: string) {
    setCuentaActiva(id === enlaceCuenta.id);
    if (id === enlaceCuenta.id || !gruposAdministracion.some((grupo) => grupo.enlaces.some((item) => item === id))) return;
    setVista(id as Seccion);
    setSeleccion(null);
    setConflicto(false);
    setRol("");
    setParticipanteId("");
  }

  return (
    <MarcoPanel grupos={secciones} activo={cuentaActiva ? enlaceCuenta.id : vista}
      titulo={cuentaActiva ? enlaceCuenta.texto : vista === "Inicio" ? "Administración" : vista}
      contexto="Administración de EcoConecta" cuenta={cuentaSesion} navegar={navegar}>
      {conflicto && (
        <p role="alert">Este registro cambió. Vuelve a seleccionarlo para revisar la versión actual.</p>
      )}
      {vista === "Sistema" ? (
        <section className="eco-tarjeta">
          <h2>Estado del sistema</h2>
          {cap.datos ? (
            <>
              <p>Versión del contrato: {cap.datos.version_contrato}</p>
              <p>Modo de avisos: {cap.datos.avisos.modo}</p>
              <p>IA en este frontend: desactivada.</p>
            </>
          ) : (
            <Espera error={cap.error} reintentar={cap.recargar} />
          )}
        </section>
      ) : vista === "Inicio" ? (
        <section className="eco-tarjeta">
          <h2>Administración de EcoConecta</h2>
          <p>Gestiona accesos, unidades y configuración del programa.</p>
          <div className="acciones">
            <button className="btn primario" onClick={() => navegar("Piloto")}>Revisar habilitaciones</button>
            <button className="btn" onClick={() => navegar("Cuentas")}>Crear cuenta</button>
          </div>
        </section>
      ) : vista === "Piloto" && !lista.datos ? (
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
          <div className="col-12 col-lg-6">
            <section className="eco-tarjeta">
              <h2>{vista}</h2>
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
                <p>Sin registros disponibles.</p>
              ) : (
                <ul className="registros">
                  {filas.map((f) => {
                    const persona = vista === "Piloto"
                      ? participantes.datos?.find((p) => p.id === f.participante_id)
                      : undefined;
                    const unidad = persona?.unidades.find((u) => u.id === f.unidad_id);
                    return (
                    <li key={f.id}>
                      <strong>
                        {(vista === "Unidades" && (f.etiqueta || f.referencia_local)) ||
                          persona?.nombre || f.nombre ||
                          f.titulo ||
                          f.referencia_local ||
                          f.codigo ||
                          f.recipiente ||
                          f.estado ||
                          "Habilitación"}
                      </strong>
                      <small>
                        {[
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
                          f.parametros?.puntos !== undefined
                            ? f.parametros.puntos + " puntos"
                            : "",
                          f.kg_por_unidad ? f.kg_por_unidad + " kg/unidad" : "",
                          f.vigente_desde && fechaBogota(new Date(f.vigente_desde)),
                          f.vigente_hasta && "Vence: " + fechaBogota(new Date(f.vigente_hasta)),
                          f.texto,
                        ]
                          .filter(Boolean)
                          .join(" · ")}
                      </small>
                      {(vista === "Piloto" || vista === "Educación" || vista === "Recolectores" || vista === "Materiales") && (
                        <button className="btn" onClick={() => { setConflicto(false); setSeleccion(f); }}>
                          {vista === "Piloto" ? "Cambiar habilitación" : "Editar"}
                        </button>
                      )}
                      {vista === "Cuentas" && (
                        <button className="btn" onClick={() => { setConflicto(false); setSeleccion(f); }}>
                          Administrar acceso
                        </button>
                      )}
                    </li>
                    );
                  })}
                </ul>
              )}
            </section>
          </div>
          <div className="col-12 col-lg-6">
            <Formulario
              key={vista + (cuenta?.id || "")}
              preparar={preparar}
              alConflicto={() => {
                setConflicto(true);
                setSeleccion(null);
                lista.recargar();
              }}
              accion="Guardar"
              titulo={
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
                  : {
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
                    }[vista]
              }
              alGuardar={() => {
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
                    <label>
                      Estado
                      <select
                        name="activo"
                        defaultValue={String(cuenta.activo)}
                      >
                        <option value="true">Activo</option>
                        <option value="false">Inactivo</option>
                      </select>
                    </label>
                    <Campo
                      nombre="pin"
                      titulo="Nuevo PIN (opcional)"
                      tipo="password"
                      opcional
                      pattern="[0-9]{4,12}"
                    />
                    <button
                      type="button"
                      className="btn"
                      onClick={() => setSeleccion(null)}
                    >
                      Volver
                    </button>
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
                        <option value="">Selecciona</option>
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
                    <label>
                      Estado
                      <select name="activo" defaultValue={String(seleccion.activo)}>
                        <option value="true">Activo</option>
                        <option value="false">Inactivo</option>
                      </select>
                    </label>
                    <button type="button" className="btn" onClick={() => setSeleccion(null)}>Volver</button>
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
                    <label>
                      <input type="checkbox" required /> La persona autorizó
                      registrar sus datos para coordinar las entregas.
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
                          <option value="">Selecciona un participante</option>
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
                  {seleccion && <button type="button" className="btn" onClick={() => setSeleccion(null)}>Volver</button>}
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
                    <button type="button" className="btn" onClick={() => setSeleccion(null)}>Volver</button>
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
                    <label>
                      Estado
                      <select name="activo" defaultValue={String(seleccion.activo)}>
                        <option value="true">Activo</option>
                        <option value="false">Inactivo</option>
                      </select>
                    </label>
                    <button type="button" className="btn" onClick={() => setSeleccion(null)}>Volver</button>
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
          </div>
        </div>
      )}
    </MarcoPanel>
  );
}
