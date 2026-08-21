"""Carga y expone las variables de entorno del proyecto (.env): URL de la API
externa de vacaciones, credenciales de modelo de IA, API keys externas, etc."""

import os

from dotenv import load_dotenv

from app.utils.logger import get_logger

load_dotenv()

logger = get_logger(__name__)

HF_TOKEN = os.getenv("HF_TOKEN")
HF_MODEL_ID = os.getenv("HF_MODEL_ID", "Qwen/Qwen2.5-Coder-32B-Instruct")

# Gemini (Google AI Studio): tiene prioridad sobre OpenRouter y HuggingFace si
# está configurada. Usa el endpoint compatible con OpenAI de Gemini, así que
# reutiliza la misma clase OpenAIServerModel (sin dependencias nuevas). Nota:
# "gemini-1.5-flash" ya no existe (generación retirada) — el equivalente
# gratuito y estable actual es gemini-2.5-flash.
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL_ID = os.getenv("GEMINI_MODEL_ID", "gemini-3.6-flash")
GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/openai/"

# Groq (console.groq.com): tier gratuito generoso (~30 RPM / 14.400
# peticiones/día; el techo real son los tokens por minuto) e inferencia muy
# rápida. API compatible con OpenAI: entra en la misma cadena de respaldo.
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
# Nota: los gpt-oss de Groq emiten tool-calls nativos (formato harmony) que
# smolagents no usa y Groq rechaza con 400 "Tool choice is none"; qwen3.6
# responde texto plano y funciona con CodeAgent.
GROQ_MODEL_ID = os.getenv("GROQ_MODEL_ID", "qwen/qwen3.6-27b")
GROQ_API_BASE = "https://api.groq.com/openai/v1"

# Cerebras (cloud.cerebras.ai): otro tier gratuito rápido (~30 RPM /
# 1M tokens/día). Suele servir el mismo gpt-oss-120b que Groq, pero con
# cuota independiente: un eslabón más antes de caer a los ":free" de
# OpenRouter, que son los menos confiables.
CEREBRAS_API_KEY = os.getenv("CEREBRAS_API_KEY")
CEREBRAS_MODEL_ID = os.getenv("CEREBRAS_MODEL_ID", "gpt-oss-120b")
CEREBRAS_API_BASE = "https://api.cerebras.ai/v1"

# OpenRouter: alternativa a HuggingFace Inference cuando esta se queda sin
# crédito mensual (error 402). Si OPENROUTER_API_KEY está configurada, tiene
# prioridad sobre HF_TOKEN.
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL_ID = os.getenv("OPENROUTER_MODEL_ID", "qwen/qwen-2.5-coder-32b-instruct")
# Cadena de modelos gratuitos de respaldo (separados por coma, en orden de
# prioridad): si el principal falla (sin cupo del momento, rate limit del
# tier gratuito, error temporal del proveedor — los modelos ":free" de
# OpenRouter se saturan y quedan no disponibles de forma intermitente), se
# reintenta automáticamente con el siguiente de la lista antes de devolver el
# error al usuario.
OPENROUTER_FALLBACK_MODEL_IDS = [
    m.strip() for m in os.getenv("OPENROUTER_FALLBACK_MODEL_IDS", "").split(",") if m.strip()
]

# Límite de pasos por agente: cada paso es una llamada al modelo LLM que
# reenvía todo el historial de la conversación, así que estos valores acotan
# el consumo de tokens por mensaje. Si son muy bajos, el agente puede cortar
# a mitad de tarea sin llegar a la respuesta final.
def _int_entorno(nombre, default):
    valor = os.getenv(nombre)
    if not valor:
        return default
    try:
        return int(valor)
    except ValueError:
        logger.warning(
            "%s=%r no es un número entero; usando el valor por defecto %s.",
            nombre,
            valor,
            default,
        )
        return default


MAX_STEPS_ORQUESTADOR = _int_entorno("MAX_STEPS_ORQUESTADOR", 10)
MAX_STEPS_SOLICITUDES = _int_entorno("MAX_STEPS_SOLICITUDES", 4)
MAX_STEPS_VIAJE = _int_entorno("MAX_STEPS_VIAJE", 8)

# Puerto real del perfil "http" en launchSettings.json del sistema C# MVC
# (Sali_Vacaciones), no 5000 como asumía el contrato original.
VACACIONES_API_URL = os.getenv("VACACIONES_API_URL", "http://localhost:5051")
VACACIONES_API_KEY = os.getenv("VACACIONES_API_KEY")
CORS_ALLOWED_ORIGIN = os.getenv("CORS_ALLOWED_ORIGIN", "http://localhost:5001")

_model = None


class CadenaDeModelos:
    """Envuelve una lista de modelos para smolagents e intenta cada uno en
    orden hasta que alguno responda. Pensado para modelos gratuitos de
    OpenRouter, que se saturan (su cupo gratuito del momento se agota) y
    devuelven 404 "unavailable for free" de forma intermitente — encadenar
    varios reduce las chances de que una petición completa falle por eso."""

    def __init__(self, modelos):
        if not modelos:
            raise ValueError("CadenaDeModelos necesita al menos un modelo.")
        self.modelos = modelos

    @property
    def model_id(self):
        return self.modelos[0].model_id

    def generate(self, *args, **kwargs):
        ultimo_error = None
        for i, modelo in enumerate(self.modelos):
            try:
                return modelo.generate(*args, **kwargs)
            except Exception as exc:
                ultimo_error = exc
                if i < len(self.modelos) - 1:
                    logger.warning(
                        "Modelo %s falló (%s); probando el siguiente de la cadena (%s).",
                        modelo.model_id,
                        exc,
                        self.modelos[i + 1].model_id,
                    )
        raise ultimo_error


def get_model():
    """Devuelve una única instancia compartida del modelo LLM, como cadena de
    respaldo entre proveedores (todos con API compatible con OpenAI). Orden
    de los eslabones según las claves configuradas:
    Gemini (GEMINI_API_KEY) > Groq (GROQ_API_KEY) > Cerebras
    (CEREBRAS_API_KEY) > OpenRouter (OPENROUTER_API_KEY + sus fallbacks).
    Cuando un proveedor agota su cuota gratuita (429 RESOURCE_EXHAUSTED o
    similar), la petición salta al siguiente eslabón en vez de morir. Sin
    ninguna clave, se usa HuggingFace Inference API (HF_TOKEN).

    Todos los modelos se crean con retry=False: un 429 falla al instante y
    CadenaDeModelos prueba el siguiente eslabón, en vez de quedarse bloqueada
    esperando los reintentos internos de smolagents (60s+ por intento)."""
    global _model
    if _model is None:
        from smolagents import OpenAIServerModel

        def crear_modelo_openai(model_id, api_base, api_key):
            return OpenAIServerModel(
                model_id=model_id,
                api_base=api_base,
                api_key=api_key,
                retry=False,
                # Sin reintentos internos del SDK de OpenAI: un 429 falla al
                # instante y CadenaDeModelos pasa al siguiente proveedor. Sin
                # esto, el SDK espera los segundos del header Retry-After
                # (se vieron esperas de 22-26s con Groq) antes de fallar.
                client_kwargs={"max_retries": 0},
            )

        modelos = []
        if GEMINI_API_KEY:
            modelos.append(
                crear_modelo_openai(GEMINI_MODEL_ID, GEMINI_API_BASE, GEMINI_API_KEY)
            )
        if GROQ_API_KEY:
            modelos.append(crear_modelo_openai(GROQ_MODEL_ID, GROQ_API_BASE, GROQ_API_KEY))
        if CEREBRAS_API_KEY:
            modelos.append(
                crear_modelo_openai(CEREBRAS_MODEL_ID, CEREBRAS_API_BASE, CEREBRAS_API_KEY)
            )
        if OPENROUTER_API_KEY:
            api_base_openrouter = "https://openrouter.ai/api/v1"
            modelos.append(
                crear_modelo_openai(
                    OPENROUTER_MODEL_ID, api_base_openrouter, OPENROUTER_API_KEY
                )
            )
            modelos += [
                crear_modelo_openai(m, api_base_openrouter, OPENROUTER_API_KEY)
                for m in OPENROUTER_FALLBACK_MODEL_IDS
            ]

        if modelos:
            _model = CadenaDeModelos(modelos) if len(modelos) > 1 else modelos[0]
        else:
            from smolagents import InferenceClientModel

            if not HF_TOKEN:
                raise RuntimeError(
                    "Ni OPENROUTER_API_KEY ni HF_TOKEN están configurados. Defina uno de los "
                    "dos (vea .env.example) para poder usar el modelo LLM."
                )
            _model = InferenceClientModel(model_id=HF_MODEL_ID, token=HF_TOKEN)
    return _model
