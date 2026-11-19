import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, ErrorApi } from "./api";
import { DialogoAsignar, DialogoCierre } from "./Dialogos";
import type { Catalogo, Orden, Recolector, Sesion } from "./tipos";
import { hace } from "./util";
import { VistaBandeja, VistaHistorial, VistaRutas } from "./Vistas";

type Vista = "bandeja" | "rutas" | "historial";
export type Accion = { tipo: "asignar" | "recogida" | "rechazada"; orden: Orden };

const CADA = 15_000; // la bandeja se actualiza sola

export default function Panel({ sesion, onSalir }: { sesion: Sesion; onSalir: () => void }) {
  const gremioId = sesion.cuenta.permisos.find((p) => p.rol === "coordinacion")?.gremio_id ?? null;
  const [ordenes, setOrdenes] = useState<Orden[]>([]);
  const [recolectores, setRecolectores] = useState<Recolector[]>([]);
  const [catalogo, setCatalogo] = useState<Catalogo | null>(null);
  const [cargado, setCargado] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actualizado, setActualizado] = useState<number | null>(null);
  const [vista, setVista] = useState<Vista>("bandeja");
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
      const lista = await api.ordenes();
      setOrdenes(lista);
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
  }, [mostrar]);

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
        <div className="marca">🌱 Brota <span className="tenue">· Coordinación</span></div>
        <div className="gremio-nombre">{nombreGremio}</div>
        <div className="estado-conexion">
          {error ? <span className="error">{error}</span> : actualizado && <span className="tenue">Actualizado {hace(new Date(actualizado).toISOString())}</span>}
          <button className="btn" onClick={cargarOrdenes}>↻ Actualizar</button>
          <button className="btn" onClick={onSalir} title={sesion.cuenta.nombre}>Salir</button>
        </div>
      </header>

      <nav className="pestanas" aria-label="Secciones">
        <Pestana activa={vista === "bandeja"} onClick={() => setVista("bandeja")} cuenta={nuevas.length} alerta>
          Bandeja
        </Pestana>
        <Pestana activa={vista === "rutas"} onClick={() => setVista("rutas")} cuenta={asignadas.length}>
          Rutas de hoy
        </Pestana>
        <Pestana activa={vista === "historial"} onClick={() => setVista("historial")}>
          Historial
        </Pestana>
      </nav>

      <main className="contenido">
        {!cargado ? (
          <p className="tenue centro">Cargando solicitudes…</p>
        ) : vista === "bandeja" ? (
          <VistaBandeja nuevas={nuevas} asignadas={asignadas} {...comunes} />
        ) : vista === "rutas" ? (
          <VistaRutas asignadas={asignadas} recolectores={recolectores} {...comunes} />
        ) : (
          <VistaHistorial ordenes={ordenes} {...comunes} />
        )}
      </main>

      {accion?.tipo === "asignar" && (
        <DialogoAsignar
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
