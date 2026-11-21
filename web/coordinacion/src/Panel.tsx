import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, ErrorApi } from "./api";
import { DialogoAsignar, DialogoCierre, DialogoProgramar, Modal } from "./Dialogos";
import type { Caso, Catalogo, Orden, Recolector, Sesion } from "./tipos";
import Indicadores from "./Indicadores";
import { EquipoColectivo } from "./Equipo";
import { Pesajes } from "./Operacion";
import { Estado, fechaBogota } from "./portal";
import { MarcoPanel, Portada, TarjetaAccion, TareaPrincipal, enlaceCuenta, nombresPerfil, type CuentaPanel, type GrupoPanel } from "./MarcoPanel";
import { hace, textoFranja } from "./util";
import { Icono } from "./Iconos";
import { CanjesReservados } from "./Canjes";
import { DetalleSolicitud, VistaBandeja, VistaHistorial, VistaMisOrdenes, VistaReportes, VistaRutas } from "./Vistas";
import { Trazabilidad } from "./Trazabilidad";

const titulos = {
  inicio: "Inicio", bandeja: "Bandeja", trazabilidad: "Recorrido", rutas: "Rutas de hoy", historial: "Historial",
  reportes: "Reportes", pesajes: "Baldes y pesajes", indicadores: "Indicadores", equipo: "Equipo",
  canjes: "Canjes",
};
type Vista = keyof typeof titulos | typeof enlaceCuenta.id;
export type Accion = { tipo: "detalle" | "asignar" | "programar" | "reasignar" | "recogida" | "rechazada" | "cancelar"; orden: Orden };

const estadosOrden: Record<string, string> = { nueva: "Nueva", asignada: "Asignada", programada: "Programada" };
const iconosOrden: Record<string, string> = { nueva: "nuevo", asignada: "cuenta", programada: "calendario" };

const CADA = 15_000; // la bandeja se actualiza sola

export default function Panel({ sesion, cuenta: cuentaSesion }: { sesion: Sesion; cuenta: CuentaPanel }) {
  const { rol, salir } = cuentaSesion;
  const campo = rol === "huertero" || rol === "reciclador"; // el servidor limita `GET /v1/ordenes` a sus órdenes
  const gremioId = sesion.cuenta.permisos.find((p) => p.rol === rol)?.gremio_id ?? null;
  const [ordenes, setOrdenes] = useState<Orden[]>([]);
  const [casos, setCasos] = useState<Caso[]>([]);
  const casosConocidos = useRef<Set<string> | null>(null);
  const [recolectores, setRecolectores] = useState<Recolector[]>([]);
  const [catalogo, setCatalogo] = useState<Catalogo | null>(null);
  const [cargado, setCargado] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actualizado, setActualizado] = useState<number | null>(null);
  const [vista, setVista] = useState<Vista>("inicio");
  const [accion, setAccion] = useState<Accion | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  const [recientes, setRecientes] = useState<Set<string>>(new Set());
  const [, setReloj] = useState(0);
  const conocidas = useRef<Set<string> | null>(null);
  const temporizador = useRef<number | undefined>(undefined);

  const mostrar = useCallback((texto: string) => {
    setAviso(texto);
    window.clearTimeout(temporizador.current);
    temporizador.current = window.setTimeout(() => setAviso(null), 6000);
  }, []);

  const cargarOrdenes = useCallback(async () => {
    try {
      if (!gremioId) return;
      const [lista, reportes] = await Promise.all([api.ordenes(gremioId), campo ? Promise.resolve([]) : api.casos()]);
      setOrdenes(lista);
      setCasos(reportes.filter(c=>c.gremio_id===gremioId));
      if (casosConocidos.current) {
        const nuevos = reportes.filter((c) => c.estado === "abierto" && !casosConocidos.current!.has(c.id));
        if (nuevos.length) mostrar(`⚠ Nuevo reporte: ${nuevos.map((c) => c.codigo).join(", ")}`);
      }
      casosConocidos.current = new Set(reportes.map((c) => c.id));
      setError(null);
      setActualizado(Date.now());
      if (conocidas.current) {
        const llegaron = lista.filter((o) => o.estado === "nueva" && !conocidas.current!.has(o.id));
        if (llegaron.length) {
          setRecientes(new Set(llegaron.map((o) => o.id)));
          window.setTimeout(() => setRecientes(new Set()), 10_000);
          mostrar(`🆕 Nueva solicitud: ${llegaron.map((o) => o.codigo_pasaporte).join(", ")}`);
        }
      }
      conocidas.current = new Set(lista.map((o) => o.id));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setCargado(true);
    }
  }, [mostrar, gremioId, campo]);

  useEffect(() => {
    if (!gremioId) return;
    let vivo = true;
    Promise.all([api.catalogo(gremioId), campo ? Promise.resolve([]) : api.recolectores(gremioId)])
      .then(([c, r]) => {
        if (!vivo) return;
        setCatalogo(c);
        setRecolectores(r);
      })
      .catch((e: Error) => vivo && setError(e.message));
    cargarOrdenes();
    const intervalo = window.setInterval(cargarOrdenes, CADA);
    const reloj = window.setInterval(() => setReloj((n) => n + 1), 30_000);
    const alVolver = () => document.visibilityState === "visible" && cargarOrdenes();
    document.addEventListener("visibilitychange", alVolver);
    return () => {
      vivo = false;
      window.clearInterval(intervalo);
      window.clearInterval(reloj);
      document.removeEventListener("visibilitychange", alVolver);
    };
  }, [gremioId, campo, cargarOrdenes]);

  const servicios = useMemo(
    () => new Map((catalogo?.tipos_servicio ?? []).map((t) => [t.id, t])),
    [catalogo],
  );
  const motivos = useMemo(
    () => (catalogo?.motivos_rechazo ?? []).filter((m) => !m.gremio_id || m.gremio_id === gremioId),
    [catalogo, gremioId],
  );
  const nombreGremio = catalogo?.gremios.find((g) => g.id === gremioId)?.nombre ?? "";
  const organico = /huert|orgán/i.test(nombreGremio);
  const imagenColectivo = organico ? "huerta" : "reciclaje";
  const nuevas = ordenes.filter((o) => o.estado === "nueva");
  const asignadas = ordenes.filter((o) => o.estado === "asignada");
  const programadas = ordenes.filter((o) => o.estado === "programada");
  const abiertas = [...asignadas, ...programadas];
  const pendientes = campo ? programadas : [...nuevas, ...asignadas];
  const primerNombre = sesion.cuenta.nombre.trim().split(/\s+/)[0] || sesion.cuenta.nombre;
  // Personajes del diseño: la coordinadora de reciclaje y Viviana, de la huerta.
  const cuenta: CuentaPanel = campo ? cuentaSesion : {
    ...cuentaSesion,
    retrato: organico ? "/panel/retrato-viviana.webp" : "/panel/retrato-coordinadora.webp",
    cargo: organico ? "Coordinación de la huerta" : "Coordinación de reciclaje",
  };
  /** Qué pide el vecino, para la etiqueta de la fila: reciclable u orgánico, según lo declarado. */
  function tipoMaterial(o: Orden) {
    const nombres = [...o.residuos.map((r) => r.nombre), ...o.tipo_servicio_ids.map((id) => servicios.get(id)?.nombre ?? "")];
    const esOrganico = organico || nombres.some((n) => /org[aá]nic|c[aá]scara|comida|huerta/i.test(n));
    return esOrganico ? { texto: "Orgánico", icono: "materiales", clase: "tipo-organico" } : { texto: "Reciclable", icono: "reciclar", clase: "tipo-reciclable" };
  }

  function listo(o: Orden, texto: string) {
    setOrdenes((l) => l.map((x) => (x.id === o.id ? o : x)));
    setAccion(null);
    mostrar(texto);
    cargarOrdenes();
  }

  function conflicto(e: ErrorApi) {
    setAccion(null);
    mostrar(`⚠️ ${e.message} Actualicé la bandeja.`);
    cargarOrdenes();
  }

  if (!gremioId) {
    return (
      <main className="login">
        <div className="login-caja">
          <h1>Esta cuenta no tiene un gremio asignado</h1>
          <p className="tenue">Pide a administración que vincule tu cuenta con tu colectivo.</p>
          <button className="btn grande" onClick={salir}>Salir</button>
        </div>
      </main>
    );
  }

  const comunes = { servicios, recientes, onAccion: setAccion, campo };

  const reportesPendientes = casos.filter((c) => c.estado === "abierto").length;
  const hoy = fechaBogota(new Date());
  const rutasHoy = programadas.filter((o) => o.asignacion?.inicio &&
    fechaBogota(new Date(o.asignacion.inicio)) === hoy).length;
  const bandeja = campo ? "Mis órdenes" : titulos.bandeja;
  const grupos: GrupoPanel[] = [
    { enlaces: [{ id: "inicio", texto: titulos.inicio }] },
    { titulo: "Recolección", enlaces: campo ? [
      { id: "bandeja", texto: bandeja, cantidad: programadas.length },
      { id: "historial", texto: titulos.historial },
    ] : [
      { id: "bandeja", texto: bandeja, cantidad: nuevas.length },
      { id: "trazabilidad", texto: titulos.trazabilidad },
      { id: "rutas", texto: titulos.rutas, cantidad: rutasHoy },
      { id: "historial", texto: titulos.historial },
      { id: "reportes", texto: titulos.reportes, cantidad: reportesPendientes },
    ] },
  ];
  if (!campo) grupos.push({
    titulo: "Colectivo",
    enlaces: [
      ...(["pesajes", "indicadores", "equipo"] as const).map((id) => ({ id, texto: titulos[id] })),
      ...(organico ? [{ id: "canjes", texto: titulos.canjes }] : []),
    ],
  });
  const titulo = vista === enlaceCuenta.id ? enlaceCuenta.texto : vista === "bandeja" ? bandeja : titulos[vista];

  return (
    <>
      <MarcoPanel grupos={grupos} activo={vista} titulo={titulo} cuenta={cuenta} portada={vista === "inicio"}
        ilustracionLateral={!campo && !organico ? "/panel/caneca.webp" : undefined}
        contexto={nombreGremio || nombresPerfil[rol]} navegar={(id) => setVista(id as Vista)}
        acciones={vista !== enlaceCuenta.id && (
          <div className="panel-actualizar">
            {actualizado && !error && <span>Actualizado {hace(new Date(actualizado).toISOString())}</span>}
            <button type="button" className="btn" onClick={cargarOrdenes}>Actualizar</button>
          </div>
        )}>
        {error && <Estado tipo="error">{error}</Estado>}
        {!cargado ? (
          <Estado tipo="carga">Cargando solicitudes…</Estado>
        ) : vista === "inicio" ? (
          <>
            <Portada saludo={`¡Hola, ${primerNombre}!`}
              imagen={campo ? `/marca/${imagenColectivo}.png` : organico ? "/panel/viviana.webp" : "/panel/coordinadora.webp"}
              lado={!campo && !organico ? "izquierda" : "derecha"} mancha={!campo && !organico ? "verde" : "lila"}
              texto={campo
                ? `Tus recolecciones con ${nombreGremio || "el colectivo"}, en un solo lugar.`
                : organico
                  ? `Gestión de orgánicos – ${nombreGremio || "Huerta"}`
                  : `Gestiona las recolecciones de ${nombreGremio || "tu colectivo"} de forma fácil y rápida.`}>
              {campo ? <>
                <TarjetaAccion icono="bandeja" titulo="Ver mis órdenes" onClick={() => setVista("bandeja")} />
                <TarjetaAccion icono="historial" titulo="Ver historial" tono="turquesa"
                  onClick={() => setVista("historial")} />
              </> : organico ? <>
                <TareaPrincipal icono="pesajes" imagen="/panel/balde.webp" titulo="Registrar la entrega de baldes orgánicos"
                  texto="Lleva el control de los residuos orgánicos que recibe la huerta." />
                <TarjetaAccion icono="pesajes" titulo="Registrar baldes" tono="solido"
                  onClick={() => setVista("pesajes")} />
                <TarjetaAccion icono="entregas" titulo="Ver entregas" tono="lila"
                  onClick={() => setVista("historial")} />
              </> : <>
                <TarjetaAccion icono="bandeja" imagen="/panel/portapapeles.webp" titulo="Ver solicitudes"
                  onClick={() => setVista("bandeja")} />
                <TarjetaAccion icono="pesajes" imagen="/panel/bascula.webp" titulo="Registrar pesaje" tono="amarillo"
                  onClick={() => setVista("pesajes")} />
              </>}
            </Portada>
            <div className="resumen-operativo">
              <button type="button" onClick={() => setVista("bandeja")} className="resumen-tarea">
                <strong>{campo ? programadas.length : nuevas.length}</strong>
                <span>{campo ? "Órdenes por recoger" : "Solicitudes por asignar"}</span>
              </button>
              <button type="button" onClick={() => setVista(campo ? "bandeja" : "rutas")} className="resumen-tarea">
                <strong>{campo ? asignadas.length : rutasHoy}</strong>
                <span>{campo ? "Esperan horario" : "Visitas programadas hoy"}</span>
              </button>
              {!campo && <button type="button" onClick={() => setVista("reportes")} className="resumen-tarea">
                <strong>{reportesPendientes}</strong><span>Reportes por responder</span>
              </button>}
            </div>
            <section className="eco-tarjeta pendientes">
              <div className="pendientes-cabeza">
                <h2><Icono nombre="reciclar" />{campo ? "Próximas recolecciones" : "Solicitudes de recolección pendientes"}</h2>
                <span className="pendientes-total">
                  {pendientes.length} {pendientes.length === 1 ? "solicitud" : "solicitudes"}
                </span>
              </div>
              {pendientes.length ? (
                <ul className="pendientes-lista">
                  {pendientes.slice(0, 5).map((o) => (
                    <li key={o.id}>
                      <button type="button" className="pendiente" onClick={() => setAccion({ tipo: "detalle", orden: o })}>
                        <span className="pendiente-icono"><Icono nombre="casa" /></span>
                        <span className="pendiente-lugar">
                          <strong>{o.contacto_nombre ?? o.ubicacion_operativa}</strong>
                          <small>{o.contacto_nombre ? o.ubicacion_operativa + " · " : ""}<span className="codigo">{o.codigo_pasaporte}</span></small>
                        </span>
                        <span className="pendiente-etiquetas">
                          {!campo && (() => { const m = tipoMaterial(o); return (
                            <span className={"pendiente-material " + m.clase}><Icono nombre={m.icono} />{m.texto}</span>
                          ); })()}
                          <span className={"pendiente-tipo estado-" + o.estado}>
                            <Icono nombre={iconosOrden[o.estado] ?? "nuevo"} />{estadosOrden[o.estado] ?? o.estado}
                          </span>
                        </span>
                        <span className="pendiente-hora"><Icono nombre="reloj" />{o.asignacion?.inicio ? textoFranja(o.asignacion.inicio, o.asignacion.fin) : o.preferencia_horaria ?? hace(o.created_at)}</span>
                        <span className="pendiente-ir"><Icono nombre="chevron" /></span>
                      </button>
                    </li>
                  ))}
                </ul>
              ) : <Estado tipo="vacio">No hay solicitudes pendientes por ahora.</Estado>}
            </section>
          </>
        ) : vista === "canjes" ? <CanjesReservados />
        : vista === "trazabilidad" && !campo ? <Trazabilidad gremioFijo={gremioId} />
        : vista === "indicadores" ? <Indicadores gremioId={gremioId} />
        : vista === "pesajes" ? <Pesajes gremio={gremioId} recolectores={recolectores} />
        : vista === "equipo" ? (
          <EquipoColectivo gremioId={gremioId} organico={organico} recolectores={recolectores} abiertas={abiertas}
            recargar={() => { api.recolectores(gremioId).then(setRecolectores).catch((e: Error) => setError(e.message)); }} />
        )
        : vista === "bandeja" && campo ? (
          <VistaMisOrdenes ordenes={ordenes} {...comunes} />
        ) : vista === "bandeja" ? (
          <VistaBandeja nuevas={nuevas} asignadas={asignadas} programadas={programadas} {...comunes} />
        ) : vista === "rutas" ? (
          <VistaRutas asignadas={abiertas} recolectores={recolectores} {...comunes} />
        ) : vista === "reportes" ? (
          <VistaReportes
            casos={casos}
            onRespondido={(c) => {
              setCasos((l) => l.map((x) => (x.id === c.id ? c : x)));
              mostrar(`✅ Respuesta registrada para ${c.contacto_nombre ?? "el vecino"} (${c.codigo}).`);
            }}
            onConflicto={conflicto}
          />
        ) : (
          <VistaHistorial ordenes={ordenes} {...comunes} />
        )}
      </MarcoPanel>

      {accion?.tipo === "detalle" && <Modal titulo="Detalle de la solicitud" onCerrar={() => setAccion(null)}>
        <DetalleSolicitud id={accion.orden.id} {...comunes} />
      </Modal>}
      {accion?.tipo === "cancelar" && <Modal titulo="Cancelar recolección" onCerrar={() => setAccion(null)}>
        <p>Solicitud {accion.orden.codigo_pasaporte}. El vecino puede cancelarla desde su conversación con Brisa en WhatsApp.</p>
        <p>La cancelación desde coordinación aún no está habilitada.</p>
        <button className="btn" onClick={() => setAccion(null)}>Volver</button>
      </Modal>}
      {!campo && (accion?.tipo === "asignar" || accion?.tipo === "reasignar") && (
        <DialogoAsignar
          modo={accion.tipo}
          orden={accion.orden}
          recolectores={recolectores}
          onListo={listo}
          onConflicto={conflicto}
          onCerrar={() => setAccion(null)}
        />
      )}
      {!campo && accion?.tipo === "programar" && (
        <DialogoProgramar
          orden={accion.orden}
          onListo={listo}
          onConflicto={conflicto}
          onCerrar={() => setAccion(null)}
        />
      )}
      {(accion?.tipo === "recogida" || accion?.tipo === "rechazada") && (
        <DialogoCierre
          orden={accion.orden}
          tipo={accion.tipo}
          motivos={motivos}
          materiales={catalogo?.materiales.filter(m=>m.gremio_id===gremioId)??[]}
          onListo={listo}
          onConflicto={conflicto}
          onCerrar={() => setAccion(null)}
        />
      )}

      <div className={`toast ${aviso ? "visible" : ""}`} role="status" aria-live="polite" data-motion="notice" data-state={aviso ? "open" : "closed"}>
        {aviso}
      </div>
    </>
  );
}
