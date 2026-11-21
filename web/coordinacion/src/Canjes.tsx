import { useState } from "react";
import { pedir } from "./api";
import { Campo, Formulario } from "./Formulario";
import { Espera, Estado, useDatos } from "./portal";
import type { Catalogo } from "./tipos";
import { claveNueva } from "./util";

interface Aliado {
  id: string;
  nombre: string;
  gremio_id: string;
  activo: boolean;
}

interface ItemCanje {
  id: string;
  aliado_nombre: string;
  nombre: string;
  costo_puntos: string;
  existencias: number | null;
  activo: boolean;
}

interface CanjeReservado {
  id: string;
  participante_nombre: string;
  item_nombre: string;
  aliado_nombre: string;
  cantidad: number;
  total_puntos: string;
}

export function CanjesAdmin() {
  const catalogo = useDatos<Catalogo>("/v1/catalogos");
  const aliados = useDatos<Aliado[]>("/v1/aliados?limit=100");
  const items = useDatos<ItemCanje[]>("/v1/items-canje?limit=100");
  if (!catalogo.datos || !aliados.datos || !items.datos) {
    return (
      <Espera
        error={catalogo.error || aliados.error || items.error}
        reintentar={() => {
          catalogo.recargar();
          aliados.recargar();
          items.recargar();
        }}
      />
    );
  }
  const opcionesGremio = catalogo.datos.gremios.map((g) => [g.id, g.nombre] as [string, string]);
  const opcionesAliado = aliados.datos.filter((a) => a.activo).map((a) => [a.id, a.nombre] as [string, string]);
  return (
    <div className="row g-3">
      <div className="col-12 col-lg-6">
        <Formulario
          titulo="Nuevo aliado"
          accion="Crear aliado"
          preparar={(v) => ({ ruta: "aliados", cuerpo: { nombre: v.nombre, gremio_id: v.gremio_id } })}
          alGuardar={() => aliados.recargar()}
        >
          <Campo nombre="nombre" titulo="Nombre" maxLength={120} />
          <Campo nombre="gremio_id" titulo="Colectivo" opciones={opcionesGremio} />
        </Formulario>
      </div>
      <div className="col-12 col-lg-6">
        {opcionesAliado.length === 0 ? (
          <section className="eco-tarjeta">
            <h2>Nuevo premio</h2>
            <p>Primero crea un aliado. El premio colectivo de la torre no se carga aquí.</p>
          </section>
        ) : (
          <Formulario
            titulo="Nuevo premio"
            accion="Crear premio"
            preparar={(v) => ({
              ruta: "items-canje",
              cuerpo: {
                aliado_id: v.aliado_id,
                nombre: v.nombre,
                costo_puntos: v.costo_puntos,
                ...(v.existencias.trim() !== "" ? { existencias: Number(v.existencias) } : {}),
              },
            })}
            alGuardar={() => items.recargar()}
          >
            <Campo nombre="aliado_id" titulo="Aliado" opciones={opcionesAliado} />
            <Campo nombre="nombre" titulo="Nombre" maxLength={120} />
            <Campo
              nombre="costo_puntos"
              titulo="Costo en puntos (ejemplo 20.00)"
              pattern="\\d+(\\.\\d{1,2})?"
            />
            <Campo
              nombre="existencias"
              titulo="Existencias (vacío = sin control)"
              tipo="number"
              min={0}
              opcional
            />
          </Formulario>
        )}
      </div>
      <div className="col-12">
        <section className="eco-tarjeta">
          <h2>Premios</h2>
          {items.datos.length === 0 ? (
            <p>Todavía no hay premios.</p>
          ) : (
            <ul className="registros">
              {items.datos.map((item) => (
                <li key={item.id} className={item.activo ? undefined : "registro-inactivo"}>
                  <div className="registro-texto">
                    <strong>{item.nombre}</strong>
                    <span>
                      {item.aliado_nombre} · {item.costo_puntos} puntos
                      {item.existencias === null ? " · sin control de existencias" : ` · quedan ${item.existencias}`}
                      {item.activo ? "" : " · inactivo"}
                    </span>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
}

export function CanjesReservados() {
  const lista = useDatos<CanjeReservado[]>("/v1/canjes?estado=reservado&limit=100");
  const [ocupado, setOcupado] = useState<string | null>(null);
  const [aviso, setAviso] = useState<{ tipo: "exito" | "error"; texto: string } | null>(null);

  async function entregar(id: string) {
    setOcupado(id);
    setAviso(null);
    try {
      await pedir("POST", `/v1/canjes/${id}/entrega`, { cuerpo: {}, clave: claveNueva() });
      setAviso({ tipo: "exito", texto: "Canje marcado como entregado." });
      lista.recargar();
    } catch (e) {
      setAviso({ tipo: "error", texto: (e as Error).message });
    } finally {
      setOcupado(null);
    }
  }

  if (!lista.datos) return <Espera error={lista.error} reintentar={lista.recargar} />;
  return (
    <section className="eco-tarjeta">
      <h2>Canjes reservados</h2>
      <p>Cuando la persona reciba el premio, márcalo como entregado. Eso no mueve puntos.</p>
      {aviso && <Estado tipo={aviso.tipo}>{aviso.texto}</Estado>}
      {lista.datos.length === 0 ? (
        <Estado tipo="vacio">No hay canjes reservados.</Estado>
      ) : (
        <ul className="registros">
          {lista.datos.map((canje) => (
            <li key={canje.id}>
              <div className="registro-texto">
                <strong>{canje.participante_nombre}</strong>
                <span>
                  {canje.item_nombre} · {canje.aliado_nombre} · {canje.cantidad} · {canje.total_puntos} puntos
                </span>
              </div>
              <button
                type="button"
                className="btn grande"
                disabled={ocupado === canje.id}
                onClick={() => entregar(canje.id)}
              >
                {ocupado === canje.id ? "Guardando…" : "Entregado"}
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
