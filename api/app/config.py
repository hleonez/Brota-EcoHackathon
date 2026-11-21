"""Configuración de la API leída de variables de entorno (y de `api/.env` si existe)."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL

API_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=API_DIR / ".env", env_file_encoding="utf-8", extra="ignore")

    port: int = 8000
    # "/api" detrás del proxy; vacío en desarrollo directo.
    root_path: str = ""
    cors_allowed_origins: str = "http://localhost:3000,http://localhost:3001"

    db_host: str = "127.0.0.1"
    db_port: int = 5432
    db_name: str = "brota"
    db_user: str = ""
    db_password: str = ""
    # Alternativa a DB_PASSWORD: ruta de un secreto montado (Compose / Docker secrets).
    db_password_file: str = ""
    db_sslmode: str = "disable"

    # Autenticación de cuentas operadoras (tablet, paneles).
    jwt_secret: str = Field(default="", description="Secreto HS256 para sesiones de operadores")
    jwt_minutos: int = 12 * 60
    # Freno a la fuerza bruta del inicio de sesión (app/core/limite_acceso.py).
    login_max_fallos: int = 5
    login_max_fallos_ip: int = 30
    login_ventana_minutos: int = 15

    # Integración con el bot de WhatsApp.
    bot_service_token: str = ""
    avisos_modo: Literal["pull", "webhook"] = "pull"
    bot_webhook_url: str = ""
    bot_webhook_secret: str = ""
    avisos_max_intentos: int = 8
    avisos_reserva_segundos: int = 60

    # Reglas provisionales del plan (configurables).
    regla_solicitud_abierta: bool = True
    zona_horaria: str = "America/Bogota"
    politica_datos_version: str = "2026-11"

    # IA (Gemini · Google AI Studio). Sin clave, Brisa sigue con listas y sinónimos del catálogo.
    gemini_api_key: str = ""
    # Rápido y multimodal (texto, audio, foto). Si está saturado o falla, se prueba el de respaldo.
    gemini_modelo: str = "gemini-3.5-flash-lite"
    gemini_modelo_respaldo: str = "gemini-flash-lite-latest"
    gemini_url: str = "https://generativelanguage.googleapis.com/v1beta"
    ia_timeout_segundos: float = 25
    ia_media_max_mb: int = 10

    # Offline / idempotencia.
    idempotencia_retencion_horas: int = 72
    sync_max_operaciones: int = 100

    @field_validator("root_path")
    @classmethod
    def _sin_barra_final(cls, v: str) -> str:
        return v.rstrip("/")

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]

    def password(self) -> str:
        if self.db_password:
            return self.db_password
        if self.db_password_file:
            path = Path(self.db_password_file)
            if not path.is_absolute():
                path = (API_DIR / path).resolve()
            return path.read_text(encoding="utf-8").strip()
        return ""

    def database_url(self) -> URL:
        query: dict[str, str] = {}
        if self.db_sslmode:
            query["sslmode"] = self.db_sslmode
        # verify-full busca un root.crt que la imagen slim no trae. libpq usa el
        # almacén del sistema con sslrootcert=system (también vale PGSSLROOTCERT).
        if self.db_sslmode in {"verify-ca", "verify-full"}:
            query["sslrootcert"] = "system"
        return URL.create(
            "postgresql+psycopg",
            username=self.db_user or None,
            password=self.password() or None,
            host=self.db_host,
            port=self.db_port,
            database=self.db_name,
            query=query,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
