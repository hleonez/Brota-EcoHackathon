import { useState } from "react";
import { Aliados, Marca } from "./portal";
const guias = [
  [
    "Separación en casa",
    "Guarda el cartón y el papel secos. Separa las botellas y los envases aprovechables de los restos de comida. Asorescatar atiende los reciclables.",
  ],
  [
    "Orgánicos para la huerta",
    "Aparta cáscaras y restos de frutas y verduras en un recipiente. Retira bolsas, vidrio y metal. Huerta Ecorazón coordina la entrega.",
  ],
  [
    "Horarios y rutas",
    "Comparte el día y la franja en que puedes entregar el material. La coordinadora confirma quién pasa y a qué hora.",
  ],
  [
    "Cómo pedir y seguir tu recolección",
    "Abre el chat con Brisa. Indica si eres un hogar o un negocio, tu ubicación, el material y tu disponibilidad. Guarda el código de tu Pasaporte Circular para consultar el estado.",
  ],
];
export default function Comunidad({ volver }: { volver: () => void }) {
  const [tema, setTema] = useState(0);
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
              <nav className="pestanas">
                {guias.map(([t], i) => (
                  <button
                    key={t}
                    className={"pestana " + (tema === i ? "activa" : "")}
                    onClick={() => setTema(i)}
                  >
                    {t}
                  </button>
                ))}
              </nav>
              <h3>{guias[tema][0]}</h3>
              <p>{guias[tema][1]}</p>
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
