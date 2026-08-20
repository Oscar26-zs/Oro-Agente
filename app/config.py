"""Carga y expone las variables de entorno del proyecto (.env): URL de la API
externa de vacaciones, credenciales de modelo de IA, API keys externas, etc."""

import os

from dotenv import load_dotenv

load_dotenv()

HF_TOKEN = os.getenv("HF_TOKEN")
HF_MODEL_ID = os.getenv("HF_MODEL_ID", "Qwen/Qwen2.5-Coder-32B-Instruct")

# OpenRouter: alternativa a HuggingFace Inference cuando esta se queda sin
# crédito mensual (error 402). Si OPENROUTER_API_KEY está configurada, tiene
# prioridad sobre HF_TOKEN.
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL_ID = os.getenv("OPENROUTER_MODEL_ID", "qwen/qwen-2.5-coder-32b-instruct")

# Puerto real del perfil "http" en launchSettings.json del sistema C# MVC
# (Sali_Vacaciones), no 5000 como asumía el contrato original.
VACACIONES_API_URL = os.getenv("VACACIONES_API_URL", "http://localhost:5051")
VACACIONES_API_KEY = os.getenv("VACACIONES_API_KEY")
CORS_ALLOWED_ORIGIN = os.getenv("CORS_ALLOWED_ORIGIN", "http://localhost:5001")

_model = None


def get_model():
    """Devuelve una única instancia compartida del modelo LLM. Usa OpenRouter
    si OPENROUTER_API_KEY está configurada; si no, HuggingFace Inference API
    (HF_TOKEN)."""
    global _model
    if _model is None:
        if OPENROUTER_API_KEY:
            from smolagents import OpenAIServerModel

            _model = OpenAIServerModel(
                model_id=OPENROUTER_MODEL_ID,
                api_base="https://openrouter.ai/api/v1",
                api_key=OPENROUTER_API_KEY,
            )
        else:
            from smolagents import InferenceClientModel

            if not HF_TOKEN:
                raise RuntimeError(
                    "Ni OPENROUTER_API_KEY ni HF_TOKEN están configurados. Defina uno de los "
                    "dos (vea .env.example) para poder usar el modelo LLM."
                )
            _model = InferenceClientModel(model_id=HF_MODEL_ID, token=HF_TOKEN)
    return _model
