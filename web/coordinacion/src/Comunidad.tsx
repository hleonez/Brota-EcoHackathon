import { useState } from "react";
import { Aliados, Espera, Marca, useDatos } from "./portal";
import { temasEducativos, type TemaEducativo } from "./temasEducativos";

type Contenido = { id: string; titulo: string; texto: string | null };

export default function Comunidad({ volver }: { volver: () => void }) {
  const [tema, setTema] = useState<TemaEducativo>("separacion");
  const contenidos = useDatos<Contenido[]>("/v1/contenidos-educativos?tema=" + tema);
  const numero = String(import.meta.env.VITE_WHATSAPP_NUMERO || "").trim();
  return (
    <div className="portal">
      <header className="encabezado">
        <Marca />
        <button className="btn" onClick={volver}>
          Acceso del equipo
        </button>
      </header>
      <main className="container-xl">
        <p className="chip">Piloto en Brisas de San Pablo</p>
        <h1>Prepara tu entrega</h1>
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
                <p>Aún no hay contenidos publicados para este tema.</p>
              ) : (
                contenidos.datos.map(({ id, titulo, texto }) => (
                  <article key={id}>
                    <h3>{titulo}</h3>
                    {texto && <p style={{ whiteSpace: "pre-line" }}>{texto}</p>}
                  </article>
                ))
              )}
            </section>
          </div>
          <div className="col-12 col-lg-5">
            <section className="eco-tarjeta">
              <h2>Pide una recolección</h2>
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
          </div>
        </div>
      </main>
      <Aliados />
    </div>
  );
}
