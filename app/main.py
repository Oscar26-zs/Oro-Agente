"""Punto de entrada de la app FastAPI. Expone el endpoint POST /chat que recibe
los mensajes del empleado y llama al orquestador."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.clients.vacaciones_api_client import VacacionesApiError
from app.config import CORS_ALLOWED_ORIGIN
from app.models.chat import ChatRequest, ChatResponse
from app.orchestrator.orchestrator import procesar_mensaje
from app.utils.logger import get_logger

logger = get_logger(__name__)

app = FastAPI(title="Oro-Agente", description="Servicio de agentes de IA para el chat de vacaciones.")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[CORS_ALLOWED_ORIGIN],
    allow_methods=["POST"],
    allow_headers=["*"],
)


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    try:
        respuesta = procesar_mensaje(request.mensaje, request.empleadoId)
    except VacacionesApiError as exc:
        logger.warning("Error de conexión con el sistema de vacaciones: %s", exc)
        respuesta = f"No pude comunicarme con el sistema de vacaciones: {exc}"
    except Exception:
        logger.exception("Error inesperado procesando el mensaje del empleado %s", request.empleadoId)
        respuesta = "Ocurrió un error inesperado procesando tu mensaje. Intenta de nuevo más tarde."

    return ChatResponse(respuesta=respuesta)
