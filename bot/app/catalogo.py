"""Reconoce materiales en texto libre con los sinónimos de las fichas (sin IA).

«tengo unas cajas, 3 botellas de vidrio y cáscaras» → CARTON, VIDRIO, FRUVER.
Se buscan primero las frases más largas («botella de vidrio» gana a «botella») y lo que ya
coincidió se tacha, para no contar dos veces la misma palabra. Es el respaldo cuando la IA
(fase 2) no está disponible.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any


def normalizar(texto: str | None) -> str:
    t = unicodedata.normalize("NFKD", (texto or "").lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def _frases(ficha: dict[str, Any]) -> list[str]:
    return [f for f in {normalizar(s) for s in [ficha["nombre"], *ficha.get("sinonimos", [])]} if f]


def buscar(texto: str | None, fichas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Fichas mencionadas en el texto, en el orden en que aparecen."""
    t = f" {normalizar(texto)} "
    candidatos = sorted(((f, ficha) for ficha in fichas for f in _frases(ficha)), key=lambda x: -len(x[0]))
    encontradas: dict[str, tuple[int, dict[str, Any]]] = {}
    for frase, ficha in candidatos:
        # Admite plurales simples en cada palabra: «botellas de vidrio», «cajas», «limones».
        palabras = r" ".join(re.escape(w) + r"(?:e?s)?" for w in frase.split())
        patron = re.compile(r"(?<= )" + palabras + r"(?= )")
        m = patron.search(t)
        if not m:
            continue
        encontradas.setdefault(ficha["codigo"], (m.start(), ficha))
        t = t[: m.start()] + " " * (m.end() - m.start()) + t[m.end():]
    return [ficha for _, ficha in sorted(encontradas.values(), key=lambda x: x[0])]
