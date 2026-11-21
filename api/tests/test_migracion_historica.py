"""La cadena Alembic se prueba en bases desechables, nunca en la base de desarrollo."""
from __future__ import annotations

import os
import subprocess
import sys

from app.config import API_DIR


def test_upgrade_vacio_y_desde_el_esquema_anterior():
    resultado = subprocess.run(
        [sys.executable, "-m", "tests.verificar_migracion"],
        cwd=API_DIR,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        check=False,
    )
    assert resultado.returncode == 0, resultado.stdout + "\n" + resultado.stderr
