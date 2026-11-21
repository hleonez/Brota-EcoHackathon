import { useState } from "react";
import { Modal } from "./Dialogos";
import { Campo, Formulario, Pildoras } from "./Formulario";
import { Espera, fechaBogota, useDatos } from "./portal";
import type { ItemCatalogo, Recolector } from "./tipos";
import { Paginada } from "./Paginacion";
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
  return (
    <>
      {tiquete && <DetalleTiquete id={tiquete} volver={() => setTiquete(null)} />}
      <div className="row g-3">
        <div className="col-12 col-lg-6">
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
              <Paginada items={lista.datos} porPagina={6} etiqueta="mediciones">
              {(pagina) => (
              <ul className="registros">
                {pagina.map((p) => (
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
              </Paginada>
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
