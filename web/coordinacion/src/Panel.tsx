import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, ErrorApi } from "./api";
import { DialogoAsignar, DialogoCierre, Modal } from "./Dialogos";
import type { Caso, Catalogo, Orden, Recolector, Sesion } from "./tipos";
import Indicadores from "./Indicadores";
import { Pesajes } from "./Operacion";
import { Marca } from "./portal";
import { hace } from "./util";
import { DetalleSolicitud, VistaBandeja, VistaHistorial, VistaReportes, VistaRutas } from "./Vistas";

type Vista = "inicio" | "equipo" | "pesajes" | "indicadores" | "bandeja" | "rutas" | "reportes" | "historial";
export type Accion = { tipo: "detalle" | "asignar" | "programar" | "reasignar" | "recogida" | "rechazada" | "cancelar"; orden: Orden };

const CADA = 15_000; // la bandeja se actualiza sola

export default function Panel({ sesion, onSalir }: { sesion: Sesion; onSalir: () => void }) {
  const gremioId = sesion.cuenta.permisos.find((p) => p.rol === "coordinacion")?.gremio_id ?? null;
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
      const [lista, reportes] = await Promise.all([api.ordenes(gremioId), api.casos()]);
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
  }, [mostrar,gremioId]);

  useEffect(() => {
    if (!gremioId) return;
    let vivo = true;
    Promise.all([api.catalogo(gremioId), api.recolectores(gremioId)])
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
  }, [gremioId, cargarOrdenes]);

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
          <h1>Esta cuenta no coordina un gremio</h1>
          <p className="tenue">El panel de coordinación es para las cuentas de Asorescatar o de la huerta.</p>
          <button className="btn grande" onClick={onSalir}>Salir</button>
        </div>
      </main>
    );
  }

  const comunes = { servicios, recientes, onAccion: setAccion };

  return (
    <div className="app">
      <header className="barra">
        <Marca/>
        <div className="gremio-nombre">{nombreGremio}</div>
        <div className="estado-conexion">
          {error ? <span className="error">{error}</span> : actualizado && <span className="tenue">Actualizado {hace(new Date(actualizado).toISOString())}</span>}
          <button className="btn" onClick={cargarOrdenes}>↻ Actualizar</button>
          <button className="btn" onClick={onSalir} title={sesion.cuenta.nombre}>Salir</button>
        </div>
      </header>

      <nav className="pestanas" aria-label="Secciones">
        <Pestana activa={vista === "inicio"} onClick={()=>setVista("inicio")}>Inicio</Pestana>
        <Pestana activa={vista === "bandeja"} onClick={() => setVista("bandeja")} cuenta={nuevas.length} alerta>
          Bandeja
        </Pestana>
        <Pestana activa={vista === "rutas"} onClick={() => setVista("rutas")} cuenta={asignadas.length}>
          Rutas de hoy
        </Pestana>
        <Pestana activa={vista === "reportes"} onClick={() => setVista("reportes")}
          cuenta={casos.filter((c) => c.estado === "abierto").length} alerta>
          Reportes
        </Pestana>
        <Pestana activa={vista === "historial"} onClick={() => setVista("historial")}>
          Historial
        </Pestana>
        <Pestana activa={vista==="pesajes"} onClick={()=>setVista("pesajes")}>Baldes y pesajes</Pestana>
        <Pestana activa={vista==="indicadores"} onClick={()=>setVista("indicadores")}>Indicadores</Pestana>
        <Pestana activa={vista==="equipo"} onClick={()=>setVista("equipo")}>Equipo</Pestana>
      </nav>

      <main className="contenido">
        {!cargado ? (
          <p className="tenue centro">Cargando solicitudes…</p>
        ) : vista==="inicio" ? (<section className="bienvenida"><img className="personaje" alt="" src={"/marca/"+imagenColectivo+".png"}/><h1>¡Hola, {sesion.cuenta.nombre}!</h1><p>{nombreGremio}</p>{error?<p role="alert">Los indicadores están pendientes de actualización.</p>:<><h2>{nuevas.length} solicitudes por asignar</h2><p>{asignadas.filter(o=>!o.asignacion?.inicio).length} asignadas sin horario · {asignadas.filter(o=>o.asignacion?.inicio && o.asignacion.fin).length} programadas</p></>}<button className="btn primario grande" onClick={()=>setVista("bandeja")}>Ver solicitudes</button></section>)
        : vista==="indicadores" ? <Indicadores gremioId={gremioId}/>
        : vista==="pesajes" ? <Pesajes gremio={gremioId} recolectores={recolectores}/>
        : vista==="equipo" ? <section className="eco-tarjeta"><h1>Equipo de {nombreGremio}</h1><ul className="registros">{recolectores.map(r=><li key={r.id}><strong>{r.nombre}</strong><span>{asignadas.filter(o=>o.asignacion?.recolector_id===r.id).length} asignaciones vigentes</span>{r.telefono_contacto&&<a className="btn" href={"tel:"+r.telefono_contacto}>Llamar a {r.nombre}</a>}</li>)}</ul></section>
        : vista === "bandeja" ? (
          <VistaBandeja nuevas={nuevas} asignadas={asignadas} {...comunes} />
        ) : vista === "rutas" ? (
          <VistaRutas asignadas={asignadas} recolectores={recolectores} {...comunes} />
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
      </main>

      {accion?.tipo === "detalle" && <Modal titulo="Detalle de la solicitud" onCerrar={() => setAccion(null)}>
        <DetalleSolicitud id={accion.orden.id} {...comunes} />
      </Modal>}
      {accion?.tipo === "cancelar" && <Modal titulo="Cancelar recolección" onCerrar={() => setAccion(null)}>
        <p>Solicitud {accion.orden.codigo_pasaporte}. El vecino puede cancelarla desde su conversación con Brisa en WhatsApp.</p>
        <p>La cancelación desde coordinación aún no está habilitada.</p>
        <button className="btn" onClick={() => setAccion(null)}>Volver</button>
      </Modal>}
      {(accion?.tipo === "asignar" || accion?.tipo === "programar" || accion?.tipo === "reasignar") && (
        <DialogoAsignar
          modo={accion.tipo}
          orden={accion.orden}
          recolectores={recolectores}
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

      <div className={`toast ${aviso ? "visible" : ""}`} role="status" aria-live="polite">
        {aviso}
      </div>
    </div>
  );
}

function Pestana(props: { activa: boolean; onClick: () => void; cuenta?: number; alerta?: boolean; children: string }) {
  return (
    <button className={`pestana ${props.activa ? "activa" : ""}`} onClick={props.onClick} aria-current={props.activa}>
      {props.children}
      {props.cuenta !== undefined && props.cuenta > 0 && (
        <span className={`insignia ${props.alerta ? "alerta" : ""}`}>{props.cuenta}</span>
      )}
    </button>
  );
}
