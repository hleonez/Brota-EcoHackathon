import { useState } from "react";
import { Aliados, Espera, Estado, Marca, useDatos } from "./portal";
import { temasEducativos, type TemaEducativo } from "./temasEducativos";
import { Paginada } from "./Paginacion";

type Contenido = { id: string; titulo: string; texto: string | null };

export default function Comunidad({ volver }: { volver: () => void }) {
  const [tema, setTema] = useState<TemaEducativo>("separacion");
  const contenidos = useDatos<Contenido[]>("/v1/contenidos-educativos?tema=" + tema);
  const numero = String(import.meta.env.VITE_WHATSAPP_NUMERO || "").trim();
  // Datos públicos del programa (Administración → Programa). Si no cargan, el recuadro no aparece.
  const programa = useDatos<Record<string, string>>("/v1/programa");
  return (
    <div className="portal">
      <header className="encabezado">
        <Marca />
        <button className="btn" onClick={volver}>
          Acceso del equipo
        </button>
      </header>
      <main className="container-xl comunidad">
        <div className="comunidad-intro">
          <p>Piloto en Brisas de San Pablo</p>
          <h1>Prepara tu entrega</h1>
          <p>Consulta qué materiales recibe tu colectivo y cómo prepararlos para la recolección.</p>
        </div>
        <div className="row g-3">
          <div className="col-12 col-lg-7">
            <section className="eco-tarjeta">
              <h2>Guía de recolección</h2>
              <nav className="pestanas" aria-label="Temas de la guía">
                {(Object.keys(temasEducativos) as TemaEducativo[]).map((id) => (
                  <button
                    key={id}
                    className={"pestana " + (tema === id ? "activa" : "")}
                    aria-pressed={tema === id}
                    onClick={() => setTema(id)}
                  >
                    {temasEducativos[id]}
                  </button>
                ))}
              </nav>
              {!contenidos.datos ? (
                <Espera error={contenidos.error} reintentar={contenidos.recargar} />
              ) : contenidos.datos.length === 0 ? (
                <Estado tipo="vacio">Aún no hay contenidos publicados para este tema.</Estado>
              ) : (
                <Paginada items={contenidos.datos} porPagina={4} etiqueta="contenidos de la guía">
                  {(pagina) => pagina.map(({ id, titulo, texto }) => (
                    <article className="guia-articulo" key={id}>
                      <h3>{titulo}</h3>
                      {texto && <p style={{ whiteSpace: "pre-line" }}>{texto}</p>}
                    </article>
                  ))}
                </Paginada>
              )}
            </section>
          </div>
          <div className="col-12 col-lg-5">
            <section className="eco-tarjeta comunidad-brisa">
              <h2>Pide una recolección con Brisa</h2>
              <p>
                Las solicitudes del piloto se reciben por WhatsApp. El colectivo
                te confirmará la programación.
              </p>
              {/^[1-9]\d{7,14}$/.test(numero) ? (
                <a
                  className="btn primario"
                  href={
                    "https://wa.me/" +
                    numero +
                    "?text=Hola%2C%20quiero%20solicitar%20una%20recolecci%C3%B3n"
                  }
                >
                  Hablar con Brisa
                </a>
              ) : (
                <p>
                  Solicita el contacto oficial de Brisa a la coordinación de tu
                  colectivo.
                </p>
              )}
            </section>
            {programa.datos && (
              <section className="eco-tarjeta comunidad-contacto">
                <h2>Contacto y horarios</h2>
                <ul className="previa-datos">
                  {programa.datos.horario_atencion && <li><span aria-hidden="true">🕘</span>{programa.datos.horario_atencion}</li>}
                  {programa.datos.dias_recoleccion && <li><span aria-hidden="true">🗓️</span>{programa.datos.dias_recoleccion}</li>}
                  {programa.datos.telefono_contacto && <li><span aria-hidden="true">📞</span><a href={"tel:" + programa.datos.telefono_contacto.replace(/[^\d+]/g, "")}>{programa.datos.telefono_contacto}</a></li>}
                  {programa.datos.correo_contacto && <li><span aria-hidden="true">✉️</span><a href={"mailto:" + programa.datos.correo_contacto}>{programa.datos.correo_contacto}</a></li>}
                </ul>
              </section>
            )}
          </div>
        </div>
      </main>
      <Aliados />
    </div>
  );
}
