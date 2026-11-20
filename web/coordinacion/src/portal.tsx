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
export function Marco({
  titulo,
  nombre,
  salir,
  children,
}: {
  titulo: string;
  nombre: string;
  salir: () => void;
  children: ReactNode;
}) {
  return (
    <div className="portal">
      <header className="encabezado">
        <Marca />
        <div>
          {nombre}{" "}
          <button className="btn" onClick={salir}>
            Salir
          </button>
        </div>
      </header>
      <main className="container-xl">
        <h1>{titulo}</h1>
        {children}
      </main>
      <Aliados />
    </div>
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
export function Espera({
  error,
  reintentar,
}: {
  error?: string;
  reintentar: () => void;
}) {
  return error ? (
    <p role="alert">
      {error}{" "}
      <button type="button" className="btn" onClick={reintentar}>
        Reintentar
      </button>
    </p>
  ) : (
    <p role="status">Consultando…</p>
  );
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
