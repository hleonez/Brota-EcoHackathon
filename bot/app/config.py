"""Configuración del bot (variables de entorno o `bot/.env`)."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BOT_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BOT_DIR / ".env", env_file_encoding="utf-8", extra="ignore")

    port: int = 8090

    # Meta · WhatsApp Cloud API
    whatsapp_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_app_secret: str = ""
    whatsapp_verify_token: str = ""
    graph_api_version: str = "v25.0"
    graph_api_url: str = "https://graph.facebook.com"
    # true: no llama a Meta; guarda los mensajes salientes en memoria (GET /dev/mensajes).
    whatsapp_dry_run: bool = False
    # true: si un aviso cae fuera de la ventana de 24 h, se envía con plantilla aprobada.
    whatsapp_usar_plantillas: bool = False
    plantillas_idioma: str = "es"

    # API de Brota
    brota_api_url: str = "http://localhost:8000"
    bot_service_token: str = ""

    # Bucle de avisos
    avisos_activos: bool = True
    avisos_intervalo_segundos: float = 3.0
    avisos_lote: int = 10

    def graph_base(self) -> str:
        return f"{self.graph_api_url.rstrip('/')}/{self.graph_api_version}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
