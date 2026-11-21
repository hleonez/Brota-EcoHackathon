"""Freno a la fuerza bruta en `POST /v1/auth/sesiones`.

Un PIN de 4 dígitos tiene solo 10 000 combinaciones: sin freno se adivina en minutos. Se cuentan
los intentos fallidos en una ventana deslizante:

- por usuario (la defensa principal): `LOGIN_MAX_FALLOS` fallos en `LOGIN_VENTANA_MINUTOS` bloquean
  ese usuario hasta que el fallo más antiguo salga de la ventana;
- por IP (`LOGIN_MAX_FALLOS_IP`), para frenar a quien prueba muchos usuarios desde un mismo equipo.

Vive en memoria: Render corre una sola instancia de la API (render.yaml, `numInstances: 1`). Con
varias réplicas habría que moverlo a la base o a Redis. Un inicio exitoso limpia los fallos del usuario.
"""

from __future__ import annotations

import threading
import time
from collections import deque

from app.config import get_settings

_LIMITE_CLAVES = 10_000  # tope de memoria: si se supera, se descarta lo más viejo
_por_usuario: dict[str, deque[float]] = {}
_por_ip: dict[str, deque[float]] = {}
_candado = threading.Lock()


def _podar(fallos: deque[float], ahora: float, ventana: float) -> None:
    while fallos and fallos[0] <= ahora - ventana:
        fallos.popleft()


def segundos_de_espera(usuario: str, ip: str) -> int:
    """0 si puede intentar; si no, cuántos segundos faltan para el próximo intento."""
    s = get_settings()
    ventana = s.login_ventana_minutos * 60
    ahora = time.monotonic()
    espera = 0.0
    with _candado:
        for tabla, clave, maximo in ((_por_usuario, usuario, s.login_max_fallos), (_por_ip, ip, s.login_max_fallos_ip)):
            fallos = tabla.get(clave)
            if not fallos:
                continue
            _podar(fallos, ahora, ventana)
            if len(fallos) >= maximo:
                espera = max(espera, fallos[0] + ventana - ahora)
    return int(espera) + 1 if espera > 0 else 0


def registrar_fallo(usuario: str, ip: str) -> None:
    ahora = time.monotonic()
    with _candado:
        for tabla, clave in ((_por_usuario, usuario), (_por_ip, ip)):
            if clave not in tabla and len(tabla) >= _LIMITE_CLAVES:
                tabla.pop(next(iter(tabla)))
            tabla.setdefault(clave, deque(maxlen=200)).append(ahora)


def registrar_exito(usuario: str) -> None:
    with _candado:
        _por_usuario.pop(usuario, None)


def reiniciar() -> None:
    """Solo para pruebas."""
    with _candado:
        _por_usuario.clear()
        _por_ip.clear()
