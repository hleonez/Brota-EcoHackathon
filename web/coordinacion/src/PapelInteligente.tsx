import { useRef, useState, type FormEvent, type ReactNode } from "react";
import { ErrorApi, pedir } from "./api";
import { Modal } from "./Dialogos";
import { Espera, Estado, useDatos } from "./portal";
import type { ItemCatalogo, Recolector } from "./tipos";
import { claveParaEnvio } from "./util";
import "./estilo/papel-inteligente.css";

interface LineaFoto {
  material_id: string;
  kg_aceptados: string;
  kg_rechazados: string;
  motivo_rechazo_id?: string | null;
}

export interface RevisionFoto {
  dudosos?: { campo: string; confianza: number | null; detalle: string }[];
  materiales_descartados?: string[];
  advertencias?: string[];
}

export interface BorradorFoto extends RevisionFoto {
  id: string;
  version: number;
  codigo: string;
  estado: string;
  origen_captura: string;
  recolector_id: string | null;
  fecha_medicion: string;
  proveedor_referencia: string | null;
  numero_tiquete: string | null;
  lineas: LineaFoto[];
}

export type EdicionFoto =
  | { id: string; datos?: undefined }
  | { id: string; datos: BorradorFoto; vistaPrevia: string };

const MAX_BYTES = 10 * 1024 * 1024;
const FORMATO_FECHA = new Intl.DateTimeFormat("sv-SE", {
  timeZone: "America/Bogota", dateStyle: "short", timeStyle: "medium",
});

async function prepararFoto(archivo: File) {
  const bitmap = await createImageBitmap(archivo);
  const lienzo = document.createElement("canvas");
  try {
    const contexto = lienzo.getContext("2d", { alpha: false });
    if (!contexto) throw new Error("No se puede preparar la foto en este navegador.");
    const escala = Math.min(1, 2400 / Math.max(bitmap.width, bitmap.height));
    lienzo.width = Math.max(1, Math.round(bitmap.width * escala));
    lienzo.height = Math.max(1, Math.round(bitmap.height * escala));
    contexto.fillStyle = "#fff";
    contexto.fillRect(0, 0, lienzo.width, lienzo.height);
    contexto.drawImage(bitmap, 0, 0, lienzo.width, lienzo.height);
    for (const calidad of [0.9, 0.75, 0.6]) {
      const blob = await new Promise<Blob | null>((resolve) => lienzo.toBlob(resolve, "image/jpeg", calidad));
      if (blob?.type !== "image/jpeg" || blob.size > MAX_BYTES) continue;
      return await new Promise<string>((resolve, reject) => {
        const lector = new FileReader();
        lector.onload = () => resolve(String(lector.result));
        lector.onerror = () => reject(new Error("No se pudo leer la foto."));
        lector.readAsDataURL(blob);
      });
    }
    throw new Error("La foto debe ocupar como máximo 10 MB después de comprimirla.");
  } finally {
    bitmap.close();
  }
}

function instanteColombia(valor: string) {
  return (valor.length === 16 ? valor + ":00" : valor) + "-05:00";
}

function mensaje(error: unknown) {
  if (error instanceof ErrorApi && error.status === 403) {
    return "Fuera de su gremio.";
  }
  if (error instanceof ErrorApi && error.campos) {
    return Object.values(error.campos).join(" · ") || error.message;
  }
  return error instanceof Error ? error.message : "No se pudo completar la operación.";
}

export function LeerTiquete({ gremio, recolectores, cerrar, manual, listo }: {
  gremio: string;
  recolectores: Recolector[];
  cerrar: () => void;
  manual: (mensaje?: string) => void;
  listo: (datos: BorradorFoto, vistaPrevia: string) => void;
}) {
  const [foto, setFoto] = useState("");
  const [recolector, setRecolector] = useState("");
  const [fecha, setFecha] = useState("");
  const [pedirFecha, setPedirFecha] = useState(false);
  const [ocupado, setOcupado] = useState(false);
  const [error, setError] = useState("");
  const ocupadoRef = useRef(false);
  const [clave] = useState(() => claveParaEnvio());
  const campoFecha = useRef<HTMLInputElement>(null);

  async function cargar(archivo: File | undefined) {
    setFoto("");
    setFecha("");
    setPedirFecha(false);
    setError("");
    if (!archivo) return;
    ocupadoRef.current = true;
    setOcupado(true);
    try {
      setFoto(await prepararFoto(archivo));
    } catch {
      setError("No se pudo preparar la foto. Elige una imagen que el navegador pueda abrir o registra el pesaje a mano.");
    } finally {
      setOcupado(false);
      ocupadoRef.current = false;
    }
  }

  async function leer(e: FormEvent) {
    e.preventDefault();
    if (!foto || ocupadoRef.current) return;
    ocupadoRef.current = true;
    setOcupado(true);
    setError("");
    const cuerpo = {
      gremio_id: gremio,
      imagen: { mime_type: "image/jpeg", datos_base64: foto.slice(foto.indexOf(",") + 1) },
      recolector_id: recolector || null,
      fecha_medicion: fecha ? instanteColombia(fecha) : null,
    };
    try {
      const datos = await pedir<BorradorFoto>("POST", "/v1/pesajes/desde-foto", { cuerpo, clave: clave(cuerpo) });
      if (datos.estado !== "borrador" || datos.origen_captura !== "foto_ia") {
        throw new Error("La lectura no devolvió un borrador de foto para revisar.");
      }
      listo(datos, foto);
    } catch (e) {
      if (e instanceof ErrorApi) {
        if ((e.status === 503 && e.codigo === "IA_NO_DISPONIBLE") || e.status === 404 || e.status === 405) {
          manual("La lectura no está disponible. Registra el pesaje a mano.");
          return;
        }
        if (e.status === 422 && e.codigo === "TIQUETE_ILEGIBLE") {
          manual("No se leyó ninguna línea. Regístralo a mano.");
          return;
        }
        if (e.status === 422 && Object.keys(e.campos ?? {}).some((campo) =>
          campo === "fecha_medicion" || campo.endsWith(".fecha_medicion"))) {
          setPedirFecha(true);
          setError("Indica la fecha y hora de medición para reenviar esta misma foto.");
          requestAnimationFrame(() => campoFecha.current?.focus());
          return;
        }
      }
      setError(mensaje(e));
    } finally {
      setOcupado(false);
      ocupadoRef.current = false;
    }
  }

  return (
    <Modal titulo="Foto del tiquete" onCerrar={cerrar} bloquearCierre={ocupado}>
      <form onSubmit={leer} aria-busy={ocupado}>
        <p>Sube una foto legible. La vista previa se mantiene en este navegador.</p>
        <label className="campo">
          Foto del tiquete
          <input type="file" accept="image/*" capture="environment" disabled={ocupado}
            onChange={(e) => void cargar(e.currentTarget.files?.[0])} />
        </label>
        {foto && <img className="foto-tiquete" src={foto} alt="Vista previa del tiquete" />}
        <label className="campo">
          Responsable (opcional al leer)
          <select value={recolector} disabled={ocupado} onChange={(e) => setRecolector(e.target.value)}>
            <option value="">Sin seleccionar</option>
            {recolectores.map((r) => <option key={r.id} value={r.id}>{r.nombre}</option>)}
          </select>
        </label>
        {pedirFecha && (
          <label className="campo">
            Fecha y hora de medición (Colombia)
            <input ref={campoFecha} type="datetime-local" required value={fecha} disabled={ocupado}
              onChange={(e) => setFecha(e.target.value)} />
          </label>
        )}
        {error && <Estado tipo="error">{error}</Estado>}
        <div className="pie-modal">
          <button type="button" className="btn" disabled={ocupado} onClick={() => manual()}>Registrar a mano</button>
          <button className="btn primario" disabled={!foto || ocupado}>
            {ocupado ? "Procesando…" : "Leer tiquete"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

interface EditorProps {
  edicion: EdicionFoto;
  revision?: RevisionFoto;
  materiales: ItemCatalogo[];
  motivos: ItemCatalogo[];
  recolectores: Recolector[];
  cerrar: () => void;
  actualizado: () => void;
  confirmado: (id: string) => void;
}

export function RevisarTiquete({ edicion, ...props }: EditorProps) {
  const [consultar, setConsultar] = useState(!edicion.datos);
  const ruta = "/v1/pesajes/" + encodeURIComponent(edicion.id);
  const consulta = useDatos<BorradorFoto>(consultar ? ruta : "");
  const datos = consultar ? consulta.datos : edicion.datos;
  function recargar() {
    setConsultar(true);
    consulta.recargar();
  }
  if (datos?.estado === "borrador" && datos.origen_captura === "foto_ia") {
    return <EditorBorrador key={datos.version} {...props} datos={datos} ruta={ruta} recargar={recargar}
      vistaPrevia={edicion.datos ? edicion.vistaPrevia : undefined} />;
  }
  return (
    <Modal titulo="Revisar borrador de foto" onCerrar={props.cerrar}>
      {datos ? <Estado tipo="vacio">Este pesaje ya no es un borrador de foto editable.</Estado>
        : <Espera error={consulta.error} reintentar={recargar} />}
    </Modal>
  );
}

type LineaEditor = LineaFoto & { clave: number; codigoLeido?: string };

function kilos(valor: string) {
  const partes = /^(\d+)(?:\.(\d{1,3}))?$/.exec(valor.replace(/^\./, "0."));
  if (!partes) throw new Error("Usa kilos no negativos con hasta tres decimales.");
  return partes[1].replace(/^0+(?=\d)/, "") + "." + (partes[2] ?? "").padEnd(3, "0");
}

function campoFechaLocal(iso: string) {
  const fecha = new Date(iso);
  return Number.isNaN(fecha.getTime()) ? "" : FORMATO_FECHA.format(fecha).replace(" ", "T");
}

function encabezado(datos: BorradorFoto) {
  return {
    numero_tiquete: datos.numero_tiquete ?? "",
    proveedor_referencia: datos.proveedor_referencia ?? "",
    fecha: campoFechaLocal(datos.fecha_medicion),
    recolector_id: datos.recolector_id ?? "",
  };
}

function lineasBascula(lineas: LineaFoto[]) {
  return lineas.map((linea) => {
    const aceptados = kilos(linea.kg_aceptados);
    const rechazados = kilos(linea.kg_rechazados);
    return {
      material_id: linea.material_id,
      metodo_medicion: "bascula",
      kg_aceptados: aceptados,
      kg_rechazados: rechazados,
      motivo_rechazo_id: rechazados === "0.000" ? null : linea.motivo_rechazo_id ?? null,
    };
  });
}

function EditorBorrador({ datos, ruta, recargar, vistaPrevia, revision, materiales, motivos, recolectores,
  cerrar, actualizado, confirmado }: Omit<EditorProps, "edicion"> & {
  datos: BorradorFoto; ruta: string; recargar: () => void; vistaPrevia?: string;
}) {
  const [guardado, setGuardado] = useState(datos);
  const [cabecera, setCabecera] = useState(() => encabezado(datos));
  const [lineas, setLineas] = useState<LineaEditor[]>(() => datos.lineas.map((linea, i) => ({
    ...linea, clave: i, codigoLeido: materiales.find((m) => m.id === linea.material_id)?.codigo,
  })));
  const siguiente = useRef(datos.lineas.length);
  const [ocupado, setOcupado] = useState(false);
  const [conflicto, setConflicto] = useState(false);
  const [error, setError] = useState("");
  const ocupadoRef = useRef(false);
  const [clavePatch] = useState(() => claveParaEnvio());
  const [claveConfirmar] = useState(() => claveParaEnvio());
  const dudas = revision?.dudosos ?? [];
  const avisos = [...new Set([...(revision?.advertencias ?? []), ...(guardado.advertencias ?? [])])];

  function duda(campos: string[]): ReactNode {
    return dudas.filter((d) => campos.includes(d.campo)).map((d, i) => (
      <small className="detalle-dudoso" key={i}>
        Revisar{d.detalle ? ": " + d.detalle : ""}
        {typeof d.confianza === "number" && Number.isFinite(d.confianza) ? ` (${Math.round(d.confianza * 100)} %)` : ""}
      </small>
    ));
  }

  function editarLinea(clave: number, cambio: Partial<LineaFoto>) {
    setLineas((actual) => actual.map((linea) => linea.clave === clave ? { ...linea, ...cambio } : linea));
  }

  async function confirmar(e: FormEvent) {
    e.preventDefault();
    if (ocupadoRef.current || conflicto) return;
    ocupadoRef.current = true;
    setOcupado(true);
    setError("");
    try {
      if (!cabecera.recolector_id || !cabecera.fecha || !lineas.length) {
        throw new Error("Indica el responsable, la fecha y al menos una línea.");
      }
      const nuevasLineas = lineasBascula(lineas);
      if (new Set(nuevasLineas.map((linea) => linea.material_id)).size !== nuevasLineas.length) {
        throw new Error("Selecciona un material distinto en cada línea.");
      }
      for (const linea of nuevasLineas) {
        if (linea.kg_aceptados === "0.000" && linea.kg_rechazados === "0.000") {
          throw new Error("Cada línea debe tener kilos aceptados o rechazados.");
        }
        if (linea.kg_rechazados !== "0.000" && !linea.motivo_rechazo_id) {
          throw new Error("Indica el motivo de cada línea con kilos rechazados.");
        }
      }
      const original = encabezado(guardado);
      const cambiosCabecera = Object.keys(original).some((campo) =>
        cabecera[campo as keyof typeof cabecera] !== original[campo as keyof typeof original]);
      let pesaje = guardado;
      if (cambiosCabecera || JSON.stringify(nuevasLineas) !== JSON.stringify(lineasBascula(guardado.lineas))) {
        const cuerpo = {
          version_esperada: guardado.version,
          recolector_id: cabecera.recolector_id,
          fecha_medicion: cabecera.fecha === original.fecha ? guardado.fecha_medicion : instanteColombia(cabecera.fecha),
          numero_tiquete: cabecera.numero_tiquete.trim() || null,
          proveedor_referencia: cabecera.proveedor_referencia.trim() || null,
          lineas: nuevasLineas,
        };
        pesaje = await pedir<BorradorFoto>("PATCH", ruta, { cuerpo, clave: clavePatch(cuerpo) });
        setGuardado(pesaje);
        setCabecera(encabezado(pesaje));
        setLineas(pesaje.lineas.map((linea) => {
          const anterior = lineas.find((l) => l.material_id === linea.material_id);
          return { ...linea, clave: anterior?.clave ?? siguiente.current++, codigoLeido: anterior?.codigoLeido };
        }));
        actualizado();
      }
      const cuerpo = { version_esperada: pesaje.version };
      await pedir("POST", ruta + "/confirmacion", { cuerpo, clave: claveConfirmar(cuerpo) });
      confirmado(pesaje.id);
    } catch (e) {
      if (e instanceof ErrorApi && (e.codigo === "VERSION_CONFLICT" || e.codigo === "INVALID_TRANSITION")) {
        setConflicto(true);
        setError("El pesaje cambió. Carga la versión actual antes de continuar.");
        actualizado();
      } else {
        setError(mensaje(e));
      }
    } finally {
      setOcupado(false);
      ocupadoRef.current = false;
    }
  }

  return (
    <Modal titulo={`Revisar tiquete · ${datos.codigo}`} onCerrar={cerrar} bloquearCierre={ocupado}>
      <form onSubmit={confirmar} aria-busy={ocupado}>
        <p>Este pesaje está en borrador. Revisa los datos antes de confirmarlo.</p>
        {vistaPrevia && <details>
          <summary>Ver foto del tiquete</summary>
          <img className="foto-tiquete" src={vistaPrevia} alt="Vista previa del tiquete" />
        </details>}
        {!!avisos.length && <Estado tipo="carga"><ul>{avisos.map((aviso) => <li key={aviso}>{aviso}</li>)}</ul></Estado>}
        {!!revision?.materiales_descartados?.length && <Estado tipo="carga">
          Materiales descartados para este gremio: {revision.materiales_descartados.join(", ")}.
        </Estado>}
        <fieldset disabled={ocupado || conflicto}>
          <legend>Datos del tiquete</legend>
          <div className="papel-campos">
            <label className="campo">
              Número de tiquete
              <input maxLength={40} value={cabecera.numero_tiquete}
                onChange={(e) => setCabecera({ ...cabecera, numero_tiquete: e.target.value })} />
              {duda(["numero_tiquete"])}
            </label>
            <label className="campo">
              Proveedor
              <input maxLength={120} value={cabecera.proveedor_referencia}
                onChange={(e) => setCabecera({ ...cabecera, proveedor_referencia: e.target.value })} />
              {duda(["proveedor", "proveedor_referencia"])}
            </label>
            <label className="campo">
              Fecha y hora de medición (Colombia)
              <input type="datetime-local" step={1} required value={cabecera.fecha}
                onChange={(e) => setCabecera({ ...cabecera, fecha: e.target.value })} />
              {duda(["fecha", "fecha_medicion"])}
            </label>
            <label className="campo">
              Responsable
              <select required value={cabecera.recolector_id}
                onChange={(e) => setCabecera({ ...cabecera, recolector_id: e.target.value })}>
                <option value="">Selecciona un responsable</option>
                {recolectores.map((r) => <option key={r.id} value={r.id}>{r.nombre}</option>)}
              </select>
            </label>
          </div>
        </fieldset>
        <fieldset className="papel-lineas" disabled={ocupado || conflicto}>
          <legend>Líneas de báscula</legend>
          {lineas.map((linea, i) => (
            <fieldset className="papel-linea" key={linea.clave}>
              <legend>Material {i + 1}</legend>
              <div className="papel-campos">
                <label className="campo">
                  Material
                  <select required value={linea.material_id}
                    onChange={(e) => editarLinea(linea.clave, { material_id: e.target.value })}>
                    <option value="">Selecciona un material</option>
                    {materiales.map((m) => <option key={m.id} value={m.id}>{m.nombre}</option>)}
                  </select>
                </label>
                <label className="campo">
                  Kilos aceptados
                  <input type="number" min="0" step="0.001" required value={linea.kg_aceptados}
                    onChange={(e) => editarLinea(linea.clave, { kg_aceptados: e.target.value })} />
                </label>
                <label className="campo">
                  Kilos rechazados
                  <input type="number" min="0" step="0.001" required value={linea.kg_rechazados}
                    onChange={(e) => editarLinea(linea.clave, { kg_rechazados: e.target.value })} />
                </label>
                {Number(linea.kg_rechazados) > 0 && <label className="campo">
                  Motivo del rechazo
                  <select required value={linea.motivo_rechazo_id ?? ""}
                    onChange={(e) => editarLinea(linea.clave, { motivo_rechazo_id: e.target.value || null })}>
                    <option value="">Selecciona un motivo</option>
                    {motivos.map((m) => <option key={m.id} value={m.id}>{m.nombre}</option>)}
                  </select>
                </label>}
              </div>
              {linea.codigoLeido && duda(["lineas." + linea.codigoLeido])}
              <button type="button" className="btn" disabled={lineas.length === 1}
                onClick={() => setLineas(lineas.filter((l) => l.clave !== linea.clave))}>Quitar material {i + 1}</button>
            </fieldset>
          ))}
          <button type="button" className="btn" disabled={lineas.length >= 30}
            onClick={() => {
              const clave = siguiente.current++;
              setLineas([...lineas, { clave, material_id: "", kg_aceptados: "0.000", kg_rechazados: "0.000" }]);
            }}>Agregar material</button>
        </fieldset>
        {error && <Estado tipo="error">{error}</Estado>}
        <div className="pie-modal">
          <button type="button" className="btn" onClick={cerrar} disabled={ocupado}>Volver</button>
          {conflicto
            ? <button type="button" className="btn primario" onClick={recargar}>Cargar versión actual</button>
            : <button className="btn primario" disabled={ocupado || !cabecera.recolector_id}>
              {ocupado ? "Guardando…" : "Confirmar pesaje"}
            </button>}
        </div>
      </form>
    </Modal>
  );
}
