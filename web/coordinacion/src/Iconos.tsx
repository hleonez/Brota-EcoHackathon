// Inline stroke icons (24px grid). Decorative: the visible text always carries the meaning.
const trazos: Record<string, string> = {
  inicio: "M3 11.5 12 4l9 7.5M5.5 9.5V20h5v-5.5h3V20h5V9.5",
  bandeja: "M8 4h8v3H8zM6 5.5H5a1 1 0 0 0-1 1V20a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1V6.5a1 1 0 0 0-1-1h-1M8.5 14l2.5 2.5 4.5-5",
  rutas: "M6 19a2 2 0 1 0 0-4 2 2 0 0 0 0 4ZM18 9a2 2 0 1 0 0-4 2 2 0 0 0 0 4ZM8 17h7.5a3 3 0 0 0 0-6h-7a3 3 0 0 1 0-6H16",
  historial: "M3.5 12a8.5 8.5 0 1 0 2.6-6.1M3.5 4v4h4M12 7.5V12l3 2",
  reportes: "M4 5h16v11H9l-5 4zM12 8.5v3M12 13.8v.2",
  pesajes: "M4 9h16l-1.5 10.5a1.5 1.5 0 0 1-1.5 1.3H7a1.5 1.5 0 0 1-1.5-1.3zM9 9V6.5a3 3 0 0 1 6 0V9M12 12.5v4",
  indicadores: "M4 20V10M10 20V4M16 20v-7M22 20H2",
  impacto: "M4 20V10M10 20V4M16 20v-7M22 20H2",
  equipo: "M9 11a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7ZM2.5 20a6.5 6.5 0 0 1 13 0M16 4.3a3.5 3.5 0 0 1 0 6.4M18.5 14.5A6.5 6.5 0 0 1 21.5 20",
  cuenta: "M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8ZM4 21a8 8 0 0 1 16 0",
  salir: "M15 4h4v16h-4M10 8l-4 4 4 4M6 12h10",
  cuentas: "M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8ZM4 21a8 8 0 0 1 16 0",
  "registro asistido": "M9 11a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7ZM2.5 20a6.5 6.5 0 0 1 13 0M19 8v6M16 11h6",
  piloto: "M12 3 4.5 6v5.5c0 4.5 3.2 8 7.5 9.5 4.3-1.5 7.5-5 7.5-9.5V6zM9 12l2 2 4-4",
  recolectores: "M9 11a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7ZM2.5 20a6.5 6.5 0 0 1 13 0M16 4.3a3.5 3.5 0 0 1 0 6.4M18.5 14.5A6.5 6.5 0 0 1 21.5 20",
  unidades: "M4 21V8l8-5 8 5v13M9 21v-6h6v6M3 21h18",
  "educación": "M3 7l9-4 9 4-9 4zM7 9v5c0 1.7 2.2 3 5 3s5-1.3 5-3V9M21 7v6",
  materiales: "M5 19c0-8 5-14 15-14 0 10-6 15-14 15M5 19c3-4 6-6 9-7.5",
  puntos: "M12 3l2.6 5.5 6 .8-4.4 4.1 1.1 5.9L12 16.6 6.7 19.3l1.1-5.9L3.4 9.3l6-.8z",
  motivos: "M5 5h14v14H5zM9 9l6 6M15 9l-6 6",
  equivalencias: "M4 9h16M4 15h16M8 5 4 9l4 4M16 11l4 4-4 4",
  sistema: "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6ZM19.4 13a7.6 7.6 0 0 0 0-2l2-1.5-2-3.4-2.3.9a7.5 7.5 0 0 0-1.7-1L15 3.6h-4l-.4 2.4a7.5 7.5 0 0 0-1.7 1l-2.3-.9-2 3.4 2 1.5a7.6 7.6 0 0 0 0 2l-2 1.5 2 3.4 2.3-.9c.5.4 1.1.7 1.7 1l.4 2.4h4l.4-2.4c.6-.3 1.2-.6 1.7-1l2.3.9 2-3.4z",
  menu: "M4 7h16M4 12h16M4 17h16",
  cerrar: "M6 6l12 12M18 6 6 18",
  flecha: "M5 12h14M13 6l6 6-6 6",
  chevron: "M9 6l6 6-6 6",
  reloj: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18ZM12 7v5l3 2",
  hoja: "M5 19c0-8 5-14 15-14 0 10-6 15-14 15M5 19c3-4 6-6 9-7.5",
  casa: "M3 11.5 12 4l9 7.5M5.5 9.5V20h13V9.5",
  reciclar: "M8 8.5 10.7 4a1.5 1.5 0 0 1 2.6 0L16 8.5M16 8.5l.6-2.6M16 8.5l-2.6-.4M19 12.5l2 3.4a1.5 1.5 0 0 1-1.3 2.3H14M14 18.2l2-1.8M14 18.2l2 1.8M10 18.2H4.3A1.5 1.5 0 0 1 3 15.9l2.3-3.9M5.3 12l-.7 2.6M5.3 12l2.6.5",
  nuevo: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18ZM12 8v8M8 12h8",
  calendario: "M4 6h16v14H4zM4 10h16M8 3v4M16 3v4",
  entregas: "M12 3 4 7v10l8 4 8-4V7zM4 7l8 4 8-4M12 11v10",
  campana:"M6 16V11a6 6 0 0 1 12 0v5l1.5 2h-15zM10 20a2 2 0 0 0 4 0",
  ubicacion: "M12 21s-6.5-6.2-6.5-11.5a6.5 6.5 0 0 1 13 0C18.5 14.8 12 21 12 21ZM12 12a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5Z",
  abajo: "M6 9l6 6 6-6",
  check: "M5 12.5l4.5 4.5L19 7.5",
};

export function Icono({ nombre, className }: { nombre: string; className?: string }) {
  const d = trazos[nombre.toLowerCase()] ?? trazos.hoja;
  return (
    <svg className={"icono " + (className ?? "")} viewBox="0 0 24 24" width="24" height="24" aria-hidden="true"
      focusable="false" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round">
      <path d={d} />
    </svg>
  );
}
