import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "si", "on"}


class Settings:
    def __init__(self):
        self.base_url_vacaciones_api = os.getenv(
            "BASE_URL_VACACIONES_API", "http://localhost:5000"
        ).rstrip("/")
        self.use_mock_vacaciones_api = _env_bool("USE_MOCK_VACACIONES_API", True)
        self.mock_estado = os.getenv("MOCK_ESTADO", "pendiente").strip().lower()
        self.api_key_vacaciones_api = os.getenv(
            "API_KEY_VACACIONES_API", "dev-key-vacaciones-agent1"
        ).strip()
        self.model_provider = os.getenv("MODEL_PROVIDER", "openrouter").strip()
        self.model_api_key = os.getenv("MODEL_API_KEY", "").strip()
        self.model_base_url = os.getenv(
            "MODEL_BASE_URL", "https://openrouter.ai/api/v1"
        ).rstrip("/")
        self.model_name = os.getenv("MODEL_NAME", "").strip()
        self.model_fallback = [
            m.strip()
            for m in os.getenv("MODEL_FALLBACK", "")
            .split(",")
            if m.strip()
        ]
        self.host = os.getenv("HOST", "127.0.0.1").strip()
        self.port = _env_int("PORT", 8001)
        self.cors_origins = [
            o.strip()
            for o in os.getenv("CORS_ORIGINS", "*").split(",")
            if o.strip()
        ]


settings = Settings()