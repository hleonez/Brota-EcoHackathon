import { useRef, useState } from "react";
import { ErrorApi, pedir } from "./api";
import { Modal } from "./Dialogos";
import { Campo, Formulario, Pildoras } from "./Formulario";
import { Espera, Estado, fechaBogota, useDatos } from "./portal";
import type { ItemCatalogo, Recolector } from "./tipos";
import { claveNueva } from "./util";
interface CatalogoPesaje {
  materiales: ItemCatalogo[];
  equivalencias: { id: string; recipiente: string; kg_por_unidad: string }[];
}
interface Pesaje {
  id: string;
  version: number;
  codigo: string;
  estado: string;
  fecha_medicion: string;
  recolector_nombre: string | null;
  lineas: { material_nombre: string; kg_aceptados: string }[];
}
interface Tiquete extends Pesaje {
  numero_tiquete: string | null;
  emisor_tiquete: string | null;
  totales: { kg_aceptados: string; kg_rechazados: string };
  advertencias: string[];
}
interface Dudoso {
  campo: string;
  confianza: number | null;
  detalle: string;
}
interface BorradorIa extends Pesaje {
  origen_captura: string;
  dudosos: Dudoso[];
  materiales_descartados: string[];
  numero_tiquete: string | null;
  proveedor_referencia: string | null;
}
const amarillo = {
  background: "var(--eco-yellow-100)",
  color: "var(--eco-yellow-ink)",
  padding: "8px 12px",
  borderRadius: 12,
  margin: "6px 0",
} as const;

function archivoABase64(archivo: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const lector = new FileReader();
    lector.onload = () => {
      const texto = String(lector.result ?? "");
      const coma = texto.indexOf(",");
      resolve(coma >= 0 ? texto.slice(coma + 1) : texto);
    };
    lector.onerror = () => reject(lector.error ?? new Error("No se pudo leer la imagen"));
    lector.readAsDataURL(archivo);
  });
}

function lineaDudosa(nombre: string, dudosos: Dudoso[]): boolean {
  const normalizado = nombre.toLocaleUpperCase("es-CO");
  return dudosos.some((d) => {
    if (!d.campo.startsWith("lineas.") || !d.detalle.includes("por debajo de 0.6")) return false;
    return normalizado.includes(d.campo.slice("lineas.".length).toLocaleUpperCase("es-CO"));
  });
}

function CapturaPesaje({
  gremio,
  recolectores,
  alProponer,
}: {
  gremio: string;
  recolectores: Recolector[];
  alProponer: (borrador: BorradorIa) => void;
}) {
  const archivoRef = useRef<HTMLInputElement>(null);
  const [frase, setFrase] = useState("");
  const [recolector, setRecolector] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const [aviso, setAviso] = useState("");
  const [borrador, setBorrador] = useState<BorradorIa | null>(null);

  async function enviar(ruta: string, cuerpo: Record<string, unknown>) {
    setOcupado(true);
    setAviso("");
    try {
      const propuesto = await pedir<BorradorIa>("POST", ruta, { cuerpo, clave: claveNueva() });
      setBorrador(propuesto);
      alProponer(propuesto);
    } catch (e) {
      if (e instanceof ErrorApi && e.status === 503) {
        setAviso("La IA no está disponible. Registra el pesaje a mano.");
      } else {
        setAviso(e instanceof Error ? e.message : "No se pudo leer el pesaje.");
      }
    } finally {
      setOcupado(false);
    }
  }

  async function leerTiquete(archivo: File) {
    const mime = archivo.type || "image/jpeg";
    if (!mime.startsWith("image/")) {
      setAviso("Elige una imagen del tiquete. Si la IA no está, regístralo a mano.");
      return;
    }
    const datos = await archivoABase64(archivo);
    await enviar("/v1/pesajes/desde-foto", {
      gremio_id: gremio,
      fecha_medicion: new Date().toISOString(),
      ...(recolector ? { recolector_id: recolector } : {}),
      imagen: { mime_type: mime, datos_base64: datos },
    });
  }

  return (
    <section className="eco-tarjeta">
      <h2>Leer o dictar</h2>
      <label>
        Responsable
        <select value={recolector} onChange={(e) => setRecolector(e.target.value)}>
          <option value="">Sin responsable</option>
          {recolectores.map((r) => (
            <option key={r.id} value={r.id}>{r.nombre}</option>
          ))}
        </select>
      </label>
      <input
        ref={archivoRef}
        type="file"
        accept="image/*"
        hidden
        onChange={(e) => {
          const archivo = e.target.files?.[0];
          e.target.value = "";
          if (archivo) void leerTiquete(archivo);
        }}
      />
      <button type="button" className="btn primario" disabled={ocupado} onClick={() => archivoRef.current?.click()}>
        Leer tiquete
      </button>
      <label>
        Dictar pesaje
        <textarea
          value={frase}
          maxLength={2000}
          rows={3}
          placeholder="Rosa trajo 9 kg de cartón y 3 de PET"
          onChange={(e) => setFrase(e.target.value)}
        />
      </label>
      <button
        type="button"
        className="btn"
        disabled={ocupado || !frase.trim()}
        onClick={() =>
          void enviar("/v1/pesajes/desde-dictado", {
            gremio_id: gremio,
            texto: frase.trim(),
            fecha_medicion: new Date().toISOString(),
            ...(recolector ? { recolector_id: recolector } : {}),
          })
        }
      >
        Crear borrador
      </button>
      {aviso && <Estado tipo="error">{aviso}</Estado>}
      {borrador && (
        <div>
          <p>
            <strong>{borrador.codigo}</strong> · borrador
            {borrador.numero_tiquete ? " · tiquete " + borrador.numero_tiquete : ""}
          </p>
          <ul>
            {borrador.lineas.map((linea, i) => (
              <li key={i} style={lineaDudosa(linea.material_nombre, borrador.dudosos) ? amarillo : undefined}>
                {linea.material_nombre} · {linea.kg_aceptados} kg
              </li>
            ))}
          </ul>
          {borrador.dudosos.map((d) => (
            <p key={d.campo + d.detalle} style={amarillo}>{d.detalle}</p>
          ))}
        </div>
      )}
    </section>
  );
}

function DetalleTiquete({ id, volver }: { id: string; volver: () => void }) {
  const { datos, error, recargar } = useDatos<Tiquete>("/v1/pesajes/" + encodeURIComponent(id));
  return <Modal titulo="Tiquete Vivo" onCerrar={volver}>
    {datos ? <section className="eco-tarjeta">
      <h3>{datos.numero_tiquete ?? datos.codigo}</h3>
      <p>{fechaBogota(new Date(datos.fecha_medicion))} · {datos.estado}</p>
      {datos.emisor_tiquete && <p>Emisor: {datos.emisor_tiquete}</p>}
      <p>Responsable: {datos.recolector_nombre ?? "Sin responsable registrado"}</p>
      <ul>{datos.lineas.map((linea, i) => <li key={i}>{linea.material_nombre} · {linea.kg_aceptados} kg</li>)}</ul>
      <p><strong>{datos.totales.kg_aceptados} kg aceptados</strong> · {datos.totales.kg_rechazados} kg rechazados</p>
      {datos.advertencias.map((aviso, i) => <p key={i}>{aviso}</p>)}
    </section> : <Espera error={error} reintentar={recargar} />}
  </Modal>;
}

export function Pesajes({
  gremio,
  recolectores,
}: {
  gremio: string;
  recolectores: Recolector[];
}) {
  const c = useDatos<CatalogoPesaje>("/v1/catalogos?gremio_id=" + gremio);
  const lista = useDatos<Pesaje[]>("/v1/pesajes?limit=100&gremio_id=" + gremio);
  const [metodo, setMetodo] = useState("bascula");
  const [tiquete, setTiquete] = useState<string | null>(null);
  const [confirmar, setConfirmar] = useState<Pesaje | null>(null);
  const [propuesta, setPropuesta] = useState<BorradorIa | null>(null);
  return (
    <>
      {tiquete && <DetalleTiquete id={tiquete} volver={() => setTiquete(null)} />}
      <div className="row g-3">
        <div className="col-12 col-lg-6">
          <CapturaPesaje
            gremio={gremio}
            recolectores={recolectores}
            alProponer={(propuesto) => {
              setPropuesta(propuesto);
              setConfirmar(propuesto);
              lista.recargar();
            }}
          />
          {c.datos ? (
            <Formulario
              titulo="Registrar medición"
              accion="Guardar borrador"
              alGuardar={lista.recargar}
              preparar={(v) => {
                const balde = metodo === "balde";
                const linea = balde
                  ? {
                      metodo_medicion: "conversion_balde",
                      cantidad_aceptada: v.cantidad,
                      cantidad_rechazada: "0",
                      version_equivalencia_id: v.equivalencia,
                    }
                  : {
                      metodo_medicion: "bascula",
                      kg_aceptados: v.cantidad,
                      kg_rechazados: "0",
                    };
                return {
                  ruta: "pesajes",
                  cuerpo: {
                    gremio_id: gremio,
                    fecha_medicion: v.fecha + ":00-05:00",
                    origen_captura: balde ? "baldes" : "manual",
                    recolector_id: v.recolector,
                    lineas: [{ ...linea, material_id: v.material }],
                  },
                };
              }}
            >
              <Campo
                nombre="recolector"
                titulo="Responsable"
                opciones={recolectores.map((r) => [r.id, r.nombre])}
              />
              <Campo
                nombre="fecha"
                titulo="Fecha y hora de medición (Colombia)"
                tipo="datetime-local"
              />
              <Campo
                nombre="material"
                titulo="Material"
                opciones={c.datos.materiales.map((m) => [m.id, m.nombre])}
              />
              <Pildoras nombre="metodo" titulo="Método" valorInicial={metodo} onChange={setMetodo}
                opciones={[
                  ["bascula", "Báscula"],
                  ...(c.datos.equivalencias.length > 0 ? [["balde", "Conversión de baldes"] as [string, string]] : []),
                ]} />
              {metodo === "balde" && (
                <Campo
                  nombre="equivalencia"
                  titulo="Equivalencia vigente"
                  opciones={c.datos.equivalencias.map((x) => [
                    x.id,
                    x.recipiente + " · " + x.kg_por_unidad + " kg",
                  ])}
                />
              )}
              <Campo
                nombre="cantidad"
                titulo={
                  metodo === "balde" ? "Baldes aceptados" : "Kilos aceptados"
                }
                tipo="number"
                min={0.001}
                step="0.001"
              />
            </Formulario>
          ) : (
            <Espera error={c.error} reintentar={c.recargar} />
          )}
        </div>
        <div className="col-12 col-lg-6">
          <section className="eco-tarjeta">
            <h2>Registros del colectivo</h2>
            {!lista.datos ? (
              <Espera error={lista.error} reintentar={lista.recargar} />
            ) : lista.datos.length === 0 ? (
              <p>Aún no hay mediciones.</p>
            ) : (
              <ul className="registros">
                {lista.datos.map((p) => (
                  <li key={p.id}>
                    <strong>
                      {p.codigo} · {p.estado}
                    </strong>
                    <small>
                      {p.recolector_nombre} ·{" "}
                      {p.lineas
                        .map(
                          (l) =>
                            l.material_nombre + " " + l.kg_aceptados + " kg",
                        )
                        .join(", ")}
                    </small>
                    {p.estado !== "borrador" && <button className="btn" onClick={() => setTiquete(p.id)}>Ver Tiquete Vivo</button>}
                    {p.estado === "borrador" && (
                      <button className="btn" onClick={() => setConfirmar(p)}>
                        Revisar y confirmar
                      </button>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </section>
          {propuesta && confirmar?.id === propuesta.id && propuesta.dudosos.length > 0 && (
            <section className="eco-tarjeta">
              <h2>Campos por revisar</h2>
              {propuesta.dudosos.map((d) => (
                <p key={d.campo + d.detalle} style={amarillo}>{d.detalle}</p>
              ))}
            </section>
          )}
          {confirmar && (
            <Formulario
              key={confirmar.id}
              titulo={"Confirmar " + confirmar.codigo}
              preparar={() => ({
                ruta: "pesajes/" + confirmar.id + "/confirmacion",
                cuerpo: { version_esperada: confirmar.version },
              })}
              alGuardar={() => {
                setTiquete(confirmar.id);
                setConfirmar(null);
                lista.recargar();
              }}
              accion="Confirmar pesaje"
            >
              <p>
                {confirmar.lineas
                  .map((l) => l.material_nombre + ": " + l.kg_aceptados + " kg")
                  .join(", ")}
              </p>
              <button
                type="button"
                className="btn"
                onClick={() => setConfirmar(null)}
              >
                Volver
              </button>
            </Formulario>
          )}
        </div>
      </div>
    </>
  );
}
export function Avisos({ id }: { id: string }) {
  const [abierto, setAbierto] = useState(false);
  const r = useDatos<{ id: string; estado: string; tipo: string }[]>(
    abierto ? "/v1/ordenes/" + id + "/avisos" : "",
  );
  const nombres: Record<string, string> = {
    pendiente: "Pendiente de envío",
    en_envio: "En proceso",
    enviado: "Enviado",
    fallido: "No se pudo enviar",
    descartado: "Descartado",
  };
  return (
    <>
      <button
        className="btn"
        aria-expanded={abierto}
        onClick={() => setAbierto(!abierto)}
      >
        Avisos de WhatsApp
      </button>
      {abierto && (
        <div>
          {!r.datos ? (
            <Espera error={r.error} reintentar={r.recargar} />
          ) : (
            <>
              {r.datos.length === 0 ? (
                <p>Sin avisos registrados.</p>
              ) : (
                r.datos.map((a) => (
                  <p key={a.id}>
                    {a.tipo.replaceAll("_", " ")} ·{" "}
                    {nombres[a.estado] || a.estado}
                  </p>
                ))
              )}
              <button className="btn" onClick={r.recargar}>
                Actualizar estado
              </button>
            </>
          )}
        </div>
      )}
    </>
  );
}
