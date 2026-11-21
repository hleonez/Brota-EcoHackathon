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

    # Coordinación. false (por defecto): la coordinadora gestiona en el panel (web/coordinacion) y
    # por WhatsApp solo recibe la alerta de cada solicitud nueva. true: también puede asignar y
    # cerrar desde WhatsApp (respaldo si no hay tablet).
    coordinacion_por_whatsapp: bool = False
    panel_coordinacion_url: str = ""

    # Autoconexión (Docker): URL de métricas del túnel de Cloudflare (p. ej. http://tunel:2000).
    # Si está definida, el bot registra solo su webhook en Meta con la URL pública del túnel.
    tunel_metricas_url: str = ""
    # Si Meta ya apunta a una URL fija (Render, producción), el túnel local NO la reemplaza,
    # salvo que esto sea true: así correr Brota en un portátil no le quita los mensajes a producción.
    enlace_reemplazar_fijo: bool = False
    whatsapp_app_id: str = ""  # opcional: si falta, se obtiene del token
    whatsapp_waba_id: str = ""  # cuenta de WhatsApp Business (plantillas: python -m app.meta)

    # Laboratorio (solo desarrollo): http://localhost:8090/lab con celulares simulados.
    # Lo que Brisa envíe a un celular simulado se queda en el laboratorio; nunca sale a Meta.
    lab_activo: bool = False

    def graph_base(self) -> str:
        return f"{self.graph_api_url.rstrip('/')}/{self.graph_api_version}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
