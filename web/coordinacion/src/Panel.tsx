import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, ErrorApi } from "./api";
import { DialogoAsignar, DialogoCierre, DialogoProgramar, Modal } from "./Dialogos";
import type { Caso, Catalogo, Orden, Recolector, Sesion } from "./tipos";
import Indicadores from "./Indicadores";
import { Pesajes } from "./Operacion";
import { Estado, fechaBogota } from "./portal";
import { MarcoPanel, enlaceCuenta, nombresPerfil, type CuentaPanel, type GrupoPanel } from "./MarcoPanel";
import { hace } from "./util";
import { DetalleSolicitud, VistaBandeja, VistaHistorial, VistaMisOrdenes, VistaReportes, VistaRutas } from "./Vistas";

const titulos = {
  inicio: "Inicio", bandeja: "Bandeja", rutas: "Rutas de hoy", historial: "Historial",
  reportes: "Reportes", pesajes: "Baldes y pesajes", indicadores: "Indicadores", equipo: "Equipo",
};
type Vista = keyof typeof titulos | typeof enlaceCuenta.id;
export type Accion = { tipo: "detalle" | "asignar" | "programar" | "reasignar" | "recogida" | "rechazada" | "cancelar"; orden: Orden };

const CADA = 15_000; // la bandeja se actualiza sola

export default function Panel({ sesion, cuenta }: { sesion: Sesion; cuenta: CuentaPanel }) {
  const { rol, salir } = cuenta;
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
  const imagenColectivo=/huert|orgán/i.test(nombreGremio)?"huerta":"reciclaje";
  const nuevas = ordenes.filter((o) => o.estado === "nueva");
  const asignadas = ordenes.filter((o) => o.estado === "asignada");
  const programadas = ordenes.filter((o) => o.estado === "programada");
  const abiertas = [...asignadas, ...programadas];

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
      { id: "rutas", texto: titulos.rutas, cantidad: rutasHoy },
      { id: "historial", texto: titulos.historial },
      { id: "reportes", texto: titulos.reportes, cantidad: reportesPendientes },
    ] },
  ];
  if (!campo) grupos.push({
    titulo: "Colectivo",
    enlaces: (["pesajes", "indicadores", "equipo"] as const).map((id) => ({ id, texto: titulos[id] })),
  });
  const titulo = vista === enlaceCuenta.id ? enlaceCuenta.texto : vista === "bandeja" ? bandeja : titulos[vista];

  return (
    <>
      <MarcoPanel grupos={grupos} activo={vista} titulo={titulo} cuenta={cuenta}
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
            <section className="inicio-colectivo">
              <div>
                <h2>{nombreGremio || nombresPerfil[rol]}</h2>
                <p>Hola, {sesion.cuenta.nombre}.</p>
              </div>
              <img alt="" src={`/marca/${imagenColectivo}.png`} />
            </section>
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
          </>
        ) : vista === "indicadores" ? <Indicadores gremioId={gremioId} />
        : vista === "pesajes" ? <Pesajes gremio={gremioId} recolectores={recolectores} />
        : vista === "equipo" ? (
          <section className="eco-tarjeta">
            <h2>Integrantes del colectivo</h2>
            {recolectores.length ? <ul className="lista-equipo">
              {recolectores.map((r) => {
                const asignaciones = abiertas.filter((o) => o.asignacion?.recolector_id === r.id).length;
                return <li key={r.id}>
                  <div><strong>{r.nombre}</strong>
                    <span>{asignaciones} {asignaciones === 1 ? "asignación vigente" : "asignaciones vigentes"}</span></div>
                  {r.telefono_contacto && <a className="btn" href={`tel:${r.telefono_contacto}`} aria-label={`Llamar a ${r.nombre}`}>Llamar</a>}
                </li>;
              })}
            </ul> : <Estado tipo="vacio">Aún no hay integrantes activos.</Estado>}
          </section>
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

      <div className={`toast ${aviso ? "visible" : ""}`} role="status" aria-live="polite" data-motion="notice" data-state={aviso ? "visible" : "hidden"}>
        {aviso}
      </div>
    </>
  );
}
