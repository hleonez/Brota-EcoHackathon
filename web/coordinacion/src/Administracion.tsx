import { useState } from "react";
import { Campo, Formulario, type Operacion, type Valores } from "./Formulario";
import { Espera, useDatos } from "./portal";
import type { Catalogo, ItemCatalogo } from "./tipos";

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
};
const secciones = [
  "Inicio",
  "Cuentas",
  "Recolectores",
  "Unidades",
  "Registro asistido",
  "Piloto",
  "Puntos",
  "Educación",
  "Materiales",
  "Motivos",
  "Equivalencias",
  "Sistema",
] as const;
type Seccion = (typeof secciones)[number];
const rutas: Partial<Record<Seccion, string>> = {
  Cuentas: "cuentas-operadoras?limit=100",
  Recolectores: "recolectores?limit=100",
  Unidades: "unidades?limit=100",
  Piloto: "piloto/habilitaciones",
  Puntos: "configuracion?tipo=reglas_incentivo",
  Educación: "contenidos-educativos?limit=100",
  Equivalencias: "configuracion?tipo=equivalencias",
};
interface Capacidades {
  version_contrato: string;
  avisos: { modo: string };
  registro: { politica_datos_version: string };
}
export default function Administracion() {
  const [vista, setVista] = useState<Seccion>("Inicio");
  const [seleccion, setSeleccion] = useState<Fila | null>(null);
  const [rol, setRol] = useState("");
  const cat = useDatos<Catalogo & { materiales: ItemCatalogo[] }>(
    "/v1/catalogos",
  );
  const cap = useDatos<Capacidades>("/v1/capacidades");
  const lista = useDatos<Fila[]>(rutas[vista] ? "/v1/" + rutas[vista] : "");
  const unidades = useDatos<Fila[]>(
    vista === "Registro asistido" ? "/v1/unidades?limit=100" : "",
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
      case "Cuentas":
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
        return {
          ruta: "cuentas-operadoras",
          cuerpo: {
            nombre: v.nombre,
            usuario: v.usuario,
            pin: v.pin,
            permisos: [
              {
                rol: v.rol,
                gremio_id: v.rol === "coordinacion" ? v.gremio_id : null,
              },
            ],
          },
        };
      case "Recolectores":
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
      case "Piloto":
        if (seleccion) return {
          metodo: "PATCH",
          ruta: "piloto/habilitaciones/" + seleccion.id,
          cuerpo: { version_esperada: seleccion.version, vigente_hasta: v.hasta },
        };
        return {
          ruta: "piloto/habilitaciones",
          cuerpo: {
            participante_id: v.participante_id,
            unidad_id: v.unidad_id,
            vigente_desde: v.desde,
            vigente_hasta: v.hasta,
          },
        };
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
        return {
          ruta: "contenidos-educativos",
          cuerpo: {
            titulo: v.titulo,
            texto: v.texto,
            general: true,
            tipo: "texto",
          },
        };
      case "Materiales":
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
    vista === "Materiales"
      ? cat.datos?.materiales.map((m) => ({ ...m, version: 0 }))
      : vista === "Motivos"
        ? cat.datos?.motivos_rechazo.map((m) => ({ ...m, version: 0 }))
        : lista.datos;
  return (
    <>
      <div className="saludo-admin">
        <img src="/marca/administracion.png" alt="" />
        <p>Gestiona las cuentas, los contenidos y las reglas del programa.</p>
      </div>
      <nav className="pestanas" aria-label="Administración">
        {secciones.map((t) => (
          <button
            key={t}
            className={"pestana " + (t === vista ? "activa" : "")}
            onClick={() => {
              setVista(t);
              setSeleccion(null);
              setRol("");
            }}
          >
            {t}
          </button>
        ))}
      </nav>
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
            <button className="btn primario" onClick={() => setVista("Piloto")}>Revisar habilitaciones</button>
            <button className="btn" onClick={() => setVista("Cuentas")}>Crear cuenta</button>
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
                  {filas.map((f) => (
                    <li key={f.id}>
                      <strong>
                        {f.nombre ||
                          f.titulo ||
                          f.referencia_local ||
                          f.codigo ||
                          f.recipiente ||
                          f.estado ||
                          "Habilitación"}
                      </strong>
                      <small>
                        {[
                          f.usuario,
                          f.permisos?.map((p) => p.rol).join(", "),
                          f.activo === undefined
                            ? ""
                            : f.activo
                              ? "Activo"
                              : "Inactivo",
                          f.parametros?.puntos !== undefined
                            ? f.parametros.puntos + " puntos"
                            : "",
                          f.kg_por_unidad ? f.kg_por_unidad + " kg/unidad" : "",
                          f.vigente_desde?.slice(0, 10),
                          f.texto,
                        ]
                          .filter(Boolean)
                          .join(" · ")}
                      </small>
                      {(vista === "Piloto" || vista === "Educación") && (
                        <button className="btn" onClick={() => setSeleccion(f)}>
                          {vista === "Piloto" ? "Cambiar habilitación" : "Ver contenido"}
                        </button>
                      )}
                      {vista === "Cuentas" && (
                        <button className="btn" onClick={() => setSeleccion(f)}>
                          Administrar acceso
                        </button>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </div>
          <div className="col-12 col-lg-6">
            {vista === "Educación" && seleccion ? (
              <section className="eco-tarjeta">
                <h2>{seleccion.titulo}</h2>
                <p>{seleccion.texto}</p>
                <p className="tenue">La edición de contenidos publicados requiere una actualización del servidor.</p>
                <button className="btn" onClick={() => setSeleccion(null)}>Volver al editor</button>
              </section>
            ) : <Formulario
              key={vista + (cuenta?.id || "")}
              preparar={preparar}
              titulo={
                seleccion && vista === "Piloto"
                  ? "Cambiar habilitación"
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
                        <option value="fundacion">Fundación</option>
                        <option value="admin">Administración</option>
                      </select>
                    </label>
                    {rol === "coordinacion" && gremio}
                  </>
                ))}
              {vista === "Recolectores" && (
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
                        u.referencia_local || u.id,
                      ]) || []
                    }
                  />
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
                  {!seleccion && <>
                  <Campo
                    nombre="participante_id"
                    titulo="Identificador de participante"
                  />
                  <Campo
                    nombre="unidad_id"
                    titulo="Identificador de unidad vinculada"
                  />
                  <Campo nombre="desde" titulo="Desde" tipo="date" />
                  </>}
                  <Campo nombre="hasta" titulo={seleccion ? "Nueva fecha de fin" : "Hasta"} tipo="date" />
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
                <>
                  <Campo nombre="titulo" titulo="Título" maxLength={160} />
                  <Campo
                    nombre="texto"
                    titulo="Contenido educativo"
                    tipo="textarea"
                    maxLength={2000}
                  />
                </>
              )}
              {(vista === "Materiales" || vista === "Motivos") && (
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
            </Formulario>}
          </div>
        </div>
      )}
    </>
  );
}
