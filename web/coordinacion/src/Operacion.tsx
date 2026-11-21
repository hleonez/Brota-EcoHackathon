import { useEffect, useRef, useState } from "react";
import { Modal } from "./Dialogos";
import { Campo, Formulario } from "./Formulario";
import { Espera, Estado, fechaBogota, useDatos } from "./portal";
import { LeerTiquete, RevisarTiquete, type EdicionFoto, type RevisionFoto } from "./PapelInteligente";
import type { ItemCatalogo, Recolector } from "./tipos";
interface CatalogoPesaje {
  materiales: ItemCatalogo[];
  motivos_rechazo: ItemCatalogo[];
  equivalencias: { id: string; recipiente: string; kg_por_unidad: string }[];
}
interface Pesaje {
  id: string;
  version: number;
  codigo: string;
  estado: string;
  origen_captura: string;
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
  revisionesFoto,
}: {
  gremio: string;
  recolectores: Recolector[];
  revisionesFoto: Map<string, RevisionFoto>;
}) {
  const c = useDatos<CatalogoPesaje>("/v1/catalogos?gremio_id=" + gremio);
  const lista = useDatos<Pesaje[]>("/v1/pesajes?limit=100&gremio_id=" + gremio);
  const [metodo, setMetodo] = useState("bascula");
  const [tiquete, setTiquete] = useState<string | null>(null);
  const [confirmar, setConfirmar] = useState<Pesaje | null>(null);
  const [subirFoto, setSubirFoto] = useState(false);
  const [edicionFoto, setEdicionFoto] = useState<EdicionFoto | null>(null);
  const [avisoManual, setAvisoManual] = useState("");
  const zonaManual = useRef<HTMLDivElement>(null);
  const enfocarManual = useRef(false);

  useEffect(() => {
    if (!subirFoto && enfocarManual.current) {
      zonaManual.current?.querySelector<HTMLElement>("form select, form input")?.focus();
      enfocarManual.current = false;
    }
  }, [subirFoto]);

  function irAManual(aviso = "") {
    enfocarManual.current = true;
    setAvisoManual(aviso);
    setSubirFoto(false);
  }

  function abrirConfirmado(id: string) {
    revisionesFoto.delete(id);
    setEdicionFoto(null);
    setTiquete(id);
    lista.recargar();
  }

  return (
    <>
      {tiquete && <DetalleTiquete id={tiquete} volver={() => setTiquete(null)} />}
      {subirFoto && <LeerTiquete gremio={gremio} recolectores={recolectores}
        cerrar={() => setSubirFoto(false)} manual={irAManual} listo={(datos, vistaPrevia) => {
          const { dudosos, materiales_descartados, advertencias } = datos;
          revisionesFoto.set(datos.id, { dudosos, materiales_descartados, advertencias });
          setSubirFoto(false);
          setEdicionFoto({ id: datos.id, datos, vistaPrevia });
          lista.recargar();
        }} />}
      {edicionFoto && c.datos && <RevisarTiquete key={edicionFoto.id} edicion={edicionFoto}
        revision={revisionesFoto.get(edicionFoto.id)}
        materiales={c.datos.materiales.filter((material) => material.gremio_id === gremio)}
        motivos={c.datos.motivos_rechazo.filter((motivo) => !motivo.gremio_id || motivo.gremio_id === gremio)}
        recolectores={recolectores} cerrar={() => setEdicionFoto(null)} actualizado={lista.recargar}
        confirmado={abrirConfirmado} />}
      <div className="row g-3">
        <div className="col-12 col-lg-6" ref={zonaManual}>
          <section className="eco-tarjeta captura-tiquete">
            <div>
              <h2>Papel Inteligente</h2>
              <p>Lee un tiquete de báscula y revisa los datos antes de confirmar.</p>
            </div>
            <button className="btn" type="button" disabled={!c.datos} onClick={() => {
              setAvisoManual("");
              setSubirFoto(true);
            }}>Foto del tiquete</button>
          </section>
          {avisoManual && <Estado tipo="error">{avisoManual}</Estado>}
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
              <label>
                Método
                <select
                  value={metodo}
                  onChange={(e) => setMetodo(e.target.value)}
                >
                  <option value="bascula">Báscula</option>
                  {c.datos.equivalencias.length > 0 && (
                    <option value="balde">Conversión de baldes</option>
                  )}
                </select>
              </label>
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
                      <button className="btn" disabled={p.origen_captura === "foto_ia" && !c.datos} onClick={() => {
                        if (p.origen_captura === "foto_ia") {
                          setConfirmar(null);
                          setEdicionFoto({ id: p.id });
                        } else {
                          setConfirmar(p);
                        }
                      }}>
                        Revisar y confirmar
                      </button>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </section>
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
