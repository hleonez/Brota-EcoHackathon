/**
 * Paginación de listas del panel: muestra un número fijo de registros por página para que la vista
 * no crezca sin límite. Página actual, total, saltos y (en listas grandes) cuántos ver por página.
 *
 * Uso: <Paginada key={filtro} items={filas} porPagina={6} etiqueta="cuentas">
 *        {(pagina) => <ul>{pagina.map(...)}</ul>}
 *      </Paginada>
 * La `key` del padre (sección, filtro o búsqueda) devuelve a la primera página cuando cambian.
 */
import { useRef, useState, type ReactNode } from "react";
import { Icono } from "./Iconos";

const TAMANOS = [6, 12, 24];

/** Números de página con «…» cuando hay muchas: 1 … 4 5 6 … 12. */
function numeros(actual: number, total: number): (number | "…")[] {
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1);
  const cerca = [actual - 1, actual, actual + 1].filter((n) => n > 1 && n < total);
  const lista: (number | "…")[] = [1];
  if (cerca[0] > 2) lista.push("…");
  lista.push(...cerca);
  if (cerca[cerca.length - 1] < total - 1) lista.push("…");
  lista.push(total);
  return lista;
}

export function Paginada<T>({ items, porPagina = 6, etiqueta, compacta = false, children }: {
  items: readonly T[];
  porPagina?: number;
  /** Para lectores de pantalla: «Páginas de {etiqueta}». */
  etiqueta: string;
  /** Columnas angostas (bandeja, reportes): sin selector de tamaño. */
  compacta?: boolean;
  children: (pagina: T[], desde: number) => ReactNode;
}) {
  const [tamano, setTamano] = useState(porPagina);
  const [pagina, setPagina] = useState(1);
  const caja = useRef<HTMLDivElement>(null);
  const total = items.length;
  const paginas = Math.max(1, Math.ceil(total / tamano));
  const actual = Math.min(pagina, paginas);
  const desde = (actual - 1) * tamano;
  const visibles = items.slice(desde, desde + tamano);

  function ir(p: number) {
    setPagina(Math.min(Math.max(1, p), paginas));
    // Si el inicio de la lista quedó arriba de la pantalla, se vuelve a él.
    requestAnimationFrame(() => {
      const el = caja.current;
      if (el && el.getBoundingClientRect().top < 0) {
        const suave = !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        el.scrollIntoView({ block: "start", behavior: suave ? "smooth" : "auto" });
      }
    });
  }

  const hayPaginas = total > (compacta ? porPagina : Math.min(porPagina, TAMANOS[0]));
  return (
    <div className="paginada" ref={caja}>
      <div className="paginada-pagina" key={actual + "-" + tamano}>{children(visibles, desde)}</div>
      {hayPaginas && (
        <nav className={"paginacion" + (compacta ? " es-compacta" : "")} aria-label={`Páginas de ${etiqueta}`}>
          <span className="paginacion-resumen" aria-live="polite">
            {desde + 1}–{desde + visibles.length} de {total}
          </span>
          {paginas > 1 && (
            <div className="paginacion-botones">
              <button type="button" className="paginacion-paso" onClick={() => ir(actual - 1)}
                disabled={actual === 1} aria-label="Página anterior">
                <Icono nombre="chevron" className="paginacion-atras" />
              </button>
              {!compacta && numeros(actual, paginas).map((n, i) => n === "…"
                ? <span key={"e" + i} className="paginacion-salto" aria-hidden="true">…</span>
                : (
                  <button key={n} type="button" className="paginacion-numero" onClick={() => ir(n)}
                    aria-current={n === actual ? "page" : undefined} aria-label={`Página ${n}`}>
                    {n}
                  </button>
                ))}
              {compacta && <span className="paginacion-salto">{actual} / {paginas}</span>}
              <button type="button" className="paginacion-paso" onClick={() => ir(actual + 1)}
                disabled={actual === paginas} aria-label="Página siguiente">
                <Icono nombre="chevron" />
              </button>
            </div>
          )}
          {!compacta && (
            <label className="paginacion-tamano">
              Ver
              <select value={tamano} onChange={(e) => { setTamano(Number(e.target.value)); setPagina(1); }}>
                {[...new Set([porPagina, ...TAMANOS])].sort((a, b) => a - b).map((t) => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
              por página
            </label>
          )}
        </nav>
      )}
    </div>
  );
}
