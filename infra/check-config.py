"""Validate rendered Compose contracts; requires Docker Compose v2, no daemon."""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def check(env_file):
    for mode in ("dev", "server"):
        result = subprocess.run(
            [
                "docker", "compose", "--env-file", str(env_file),
                "-p", f"brota-config-{mode}",
                "-f", "infra/compose.yaml", "-f", f"infra/compose.{mode}.yaml",
                "config", "--format", "json",
            ],
            cwd=ROOT, check=True, capture_output=True, text=True,
        )
        config = json.loads(result.stdout)
        assert set(config["services"]) == {"db"}, "Unexpected application service"
        db = config["services"]["db"]
        assert db["image"] == "postgres:18.7-bookworm"
        assert "POSTGRES_PASSWORD" not in db["environment"]
        assert db["environment"]["POSTGRES_PASSWORD_FILE"] == "/run/secrets/db_password"
        assert db["healthcheck"]["test"][0] == "CMD-SHELL"
        assert any(v["type"] == "volume" and v["target"] == "/var/lib/postgresql"
                   for v in db["volumes"])
        assert config["volumes"]["postgres_data"]["name"] == f"brota-config-{mode}_postgres_data"
        ports = db.get("ports", [])
        if mode == "server":
            assert not ports, "Server must not publish PostgreSQL"
            assert db["restart"] == "unless-stopped"
        else:
            assert len(ports) == 1
            assert ports[0]["host_ip"] == "127.0.0.1"
            assert ports[0]["target"] == 5432
        print(f"Compose {mode}: OK")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python infra/check-config.py <environment-file>")
    check(Path(sys.argv[1]).resolve())
