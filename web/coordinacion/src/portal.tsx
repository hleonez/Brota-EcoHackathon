import { useEffect, useState, type ReactNode } from "react";
import { pedir } from "./api";

export function Marca() {
  return (
    <div className="identidad">
      <img src="/marca/ecoconecta.png" alt="EcoConecta Villas de San Pablo" />
      <span>Brota · Recolección comunitaria</span>
    </div>
  );
}
export function Aliados() {
  return (
    <footer className="aliados">
      <span>Una iniciativa con</span>
      <img src="/marca/fundacion.png" alt="Fundación Santo Domingo" />
      <img src="/marca/villas.png" alt="Villas de San Pablo" />
      <strong>Universidad Libre</strong>
    </footer>
  );
}
export function useDatos<T>(ruta: string) {
  const [revision, setRevision] = useState(0);
  const [estado, setEstado] = useState<{
    ruta: string;
    datos?: T;
    error?: string;
  }>({ ruta: "" });
  useEffect(() => {
    if (!ruta) return;
    let activo = true;
    setEstado({ ruta });
    pedir<T>("GET", ruta)
      .then((datos) => {
        if (activo) setEstado({ ruta, datos });
      })
      .catch((error: Error) => {
        if (activo) setEstado({ ruta, error: error.message });
      });
    return () => {
      activo = false;
    };
  }, [ruta, revision]);
  return {
    datos: estado.ruta === ruta ? estado.datos : undefined,
    error: estado.ruta === ruta ? estado.error : undefined,
    recargar: () => setRevision((r) => r + 1),
  };
}
export function Estado({ tipo, children }: { tipo: "error" | "carga" | "vacio" | "exito"; children: ReactNode }) {
  if (tipo === "vacio") return <div className="vacio">{children}</div>;
  return (
    <div className={`aviso aviso-${tipo}`} data-motion="notice" data-state="visible"
      role={tipo === "error" ? "alert" : "status"}>
      {children}
    </div>
  );
}

export function Espera({ error, reintentar }: { error?: string; reintentar: () => void }) {
  return error ? (
    <Estado tipo="error">
      <span>{error}</span>
      <button type="button" className="btn" onClick={reintentar}>Reintentar</button>
    </Estado>
  ) : <Estado tipo="carga">Consultando…</Estado>;
}
export const numero = (n: number | string) =>
  Number(n).toLocaleString("es-CO", { maximumFractionDigits: 3 });
export const fechaBogota = (fecha: Date) =>
  new Intl.DateTimeFormat("en-CA", {
    timeZone: "America/Bogota",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(fecha);
