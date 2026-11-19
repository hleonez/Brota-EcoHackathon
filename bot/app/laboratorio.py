"""Laboratorio de pruebas (solo desarrollo): http://localhost:8090/lab

Celulares simulados (vecinos y coordinación) que conversan con Brisa desde el navegador, junto
a un tablero con las órdenes y las rutas de los recolectores. Lo que Brisa envía a un celular
simulado se queda aquí y nunca sale a Meta; los celulares reales siguen yendo por WhatsApp y su
conversación también se ve (solo lectura).

Se activa con `LAB_ACTIVO=true` y solo responde a peticiones hechas desde esta misma máquina:
por el túnel de cloudflared (o cualquier proxy) devuelve 404.
"""

from __future__ import annotations

import base64
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.brota import ErrorBrota
from app.whatsapp import Entrante

PAGINA = Path(__file__).with_name("lab.html")


@dataclass(frozen=True)
class Persona:
    celular: str
    nombre: str
    rol: str  # vecino | coordinacion | real
    detalle: str
    usuario: str | None = None  # cuenta operadora que representa (coordinación)


PERSONAS = [
    Persona("573000000001", "Laura", "vecino", "Vecina nueva: se registra con Brisa"),
    Persona("573000000002", "Carlos", "vecino", "Vecino nuevo"),
    Persona("573000000003", "Sofía", "vecino", "Vecina nueva"),
    Persona("573000000101", "Coordinación Asorescatar", "coordinacion", "Reciclables · cuenta coord-reciclaje",
            "coord-reciclaje"),
    Persona("573000000102", "Coordinación Huerta Ecorazón", "coordinacion", "Orgánicos · cuenta coord-huerta",
            "coord-huerta"),
]


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


def _enmascarar(celular: str) -> str:
    return f"{celular[:4]}•••{celular[-4:]}" if len(celular) > 8 else celular


class Laboratorio:
    """Registro en memoria de las conversaciones (las simuladas y las reales)."""

    def __init__(self, maximo: int = 3000) -> None:
        self.maximo = maximo
        self.eventos: list[dict[str, Any]] = []
        self.seq = 0
        self.simulados = {p.celular for p in PERSONAS}
        self.reales: dict[str, str] = {}  # celular → nombre de perfil

    def simulado(self, celular: str) -> bool:
        return celular.lstrip("+") in self.simulados

    def _agregar(self, celular: str, direccion: str, contenido: dict[str, Any]) -> int:
        celular = celular.lstrip("+")
        if celular not in self.simulados:
            self.reales.setdefault(celular, "")
        self.seq += 1
        self.eventos.append({"seq": self.seq, "celular": celular, "dir": direccion, "hora": _ahora(), **contenido})
        del self.eventos[: -self.maximo]
        return self.seq

    def entrante(self, m: Entrante) -> None:
        if m.tipo == "text":
            contenido = {"texto": m.texto or ""}
        elif m.tipo in ("audio", "image"):
            icono = "🎤 Audio" if m.tipo == "audio" else "📸 Foto"
            contenido = {"texto": f"{icono}{': ' + m.texto if m.texto else ''}"}
        elif m.respuesta_id:
            contenido = {"texto": m.respuesta_titulo or m.respuesta_id, "respuesta_id": m.respuesta_id}
        else:
            contenido = {"texto": f"[{m.tipo}]"}
        self._agregar(m.de, "in", contenido)
        if m.nombre_perfil and not self.simulado(m.de):
            self.reales[m.de] = m.nombre_perfil

    def saliente(self, cuerpo: dict[str, Any], wamid: str | None = None) -> str:
        seq = self._agregar(cuerpo["to"], "out", {"mensaje": cuerpo})
        return wamid or f"wamid.lab.out.{seq}"

    def personas(self) -> list[dict[str, Any]]:
        salida = [asdict(p) | {"simulado": True} for p in PERSONAS]
        for cel, nombre in self.reales.items():
            salida.append({"celular": cel, "nombre": f"📱 {nombre or 'Celular real'} ({_enmascarar(cel)})",
                           "rol": "real", "detalle": "WhatsApp real · solo lectura", "usuario": None,
                           "simulado": False})
        return salida


# --------------------------------------------------------------------------- rutas


def _solo_local(request: Request) -> None:
    """Solo desde esta máquina: nada que llegue por el túnel o un proxy."""
    host = request.client.host if request.client else ""
    reenviado = any(h in request.headers for h in ("cf-connecting-ip", "x-forwarded-for", "forwarded", "x-real-ip"))
    if host not in ("127.0.0.1", "::1", "testclient") or reenviado:
        raise HTTPException(status_code=404)


class MediaLab(BaseModel):
    mime_type: str = Field(pattern=r"^(image|audio)/[\w.+-]+(;.*)?$", max_length=80)
    datos_base64: str = Field(max_length=14 * 1024 * 1024)


class MensajeIn(BaseModel):
    de: str
    texto: str | None = Field(None, max_length=4096)
    media: MediaLab | None = None
    respuesta_id: str | None = Field(None, max_length=256)
    respuesta_titulo: str | None = Field(None, max_length=72)


class PrepararIn(BaseModel):
    usuario: str = Field(min_length=1, max_length=60)
    pin: str = Field(min_length=4, max_length=12)


def montar(app: FastAPI, atender: Callable[[Entrante], Awaitable[None]]) -> None:
    r = APIRouter(prefix="/lab", dependencies=[Depends(_solo_local)], include_in_schema=False)

    @r.get("", response_class=HTMLResponse)
    async def pagina() -> str:
        return PAGINA.read_text(encoding="utf-8")

    @r.get("/estado")
    async def estado(request: Request, desde: int = 0) -> dict[str, Any]:
        lab: Laboratorio = request.app.state.lab
        return {"seq": lab.seq, "personas": lab.personas(), "eventos": [e for e in lab.eventos if e["seq"] > desde]}

    @r.post("/mensaje")
    async def mensaje(datos: MensajeIn) -> dict[str, str]:
        lab: Laboratorio = app.state.lab
        if not lab.simulado(datos.de):
            raise HTTPException(status_code=400, detail="Solo se escribe desde celulares simulados.")
        wamid = f"wamid.lab.in.{uuid.uuid4().hex}"
        if datos.media:
            tipo = "audio" if datos.media.mime_type.startswith("audio/") else "image"
            m = Entrante(wamid=wamid, de=datos.de, tipo=tipo, texto=(datos.texto or "").strip() or None,
                         media_mime=datos.media.mime_type, media_datos=base64.b64decode(datos.media.datos_base64))
        elif datos.respuesta_id:
            m = Entrante(wamid=wamid, de=datos.de, tipo="interactive", respuesta_id=datos.respuesta_id,
                         respuesta_titulo=datos.respuesta_titulo)
        elif datos.texto and datos.texto.strip():
            m = Entrante(wamid=wamid, de=datos.de, tipo="text", texto=datos.texto.strip())
        else:
            raise HTTPException(status_code=400, detail="Mensaje vacío.")
        await atender(m)  # responde cuando Brisa ya contestó
        return {"status": "ok"}

    @r.post("/preparar")
    async def preparar(datos: PrepararIn) -> dict[str, Any]:
        """Asigna a las cuentas de coordinación del seed los celulares simulados (como admin)."""
        api = app.state.api
        http = api.cliente
        r1 = await http.post(api._url("/v1/auth/sesiones"), json={"usuario": datos.usuario, "pin": datos.pin},
                             timeout=15)
        if r1.status_code != 201:
            raise HTTPException(status_code=401, detail="Usuario o PIN de administración incorrectos.")
        h = {"Authorization": f"Bearer {r1.json()['data']['token']}"}
        r2 = await http.get(api._url("/v1/cuentas-operadoras"), params={"limit": 100}, headers=h, timeout=15)
        if r2.status_code != 200:
            raise HTTPException(status_code=403, detail="Esa cuenta no es de administración.")
        cuentas = {c["usuario"]: c for c in r2.json()["data"]}
        resultado = []
        for p in PERSONAS:
            if not p.usuario:
                continue
            c = cuentas.get(p.usuario)
            if c is None:
                resultado.append({"usuario": p.usuario, "estado": "no existe (corre el seed)"})
                continue
            if c.get("celular") == "+" + p.celular:
                resultado.append({"usuario": p.usuario, "estado": "ya estaba lista"})
                continue
            r3 = await http.patch(
                api._url(f"/v1/cuentas-operadoras/{c['id']}"),
                json={"version_esperada": c["version"], "celular": p.celular},
                headers=h | {"Idempotency-Key": str(uuid.uuid4())}, timeout=15,
            )
            ok = r3.status_code == 200
            resultado.append({"usuario": p.usuario, "estado": "lista" if ok else f"error {r3.status_code}"})
        return {"data": resultado}

    @r.get("/tablero")
    async def tablero() -> dict[str, Any]:
        """Órdenes y recolectores de cada gremio, vistos con el celular simulado de su coordinación."""
        api = app.state.api
        gremios = []
        for p in PERSONAS:
            if p.rol != "coordinacion":
                continue
            g: dict[str, Any] = {"coordinacion": p.nombre, "celular": p.celular, "usuario": p.usuario,
                                 "listo": False, "ordenes": [], "recolectores": []}
            try:
                me = await api.me(p.celular)
                if me.get("tipo_actor") == "operador":
                    gremio_id = next((x["gremio_id"] for x in me.get("permisos", []) if x.get("gremio_id")), None)
                    g["listo"] = True
                    g["ordenes"] = await api.ordenes(p.celular, None, limite=100)
                    if gremio_id:
                        g["recolectores"] = await api.recolectores(p.celular, gremio_id)
            except ErrorBrota as e:
                g["error"] = e.mensaje
            except httpx.HTTPError:
                g["error"] = "La API de Brota no responde."
            gremios.append(g)
        return {"data": gremios}

    app.include_router(r)
