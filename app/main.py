import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .models.chat import ChatRequest, ChatResponse
from .orchestrator.orchestrator import Orchestrator
from .utils.logger import get_logger

logger = get_logger(__name__)

app = FastAPI(title="Oro-Agente", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

orquestador = Orchestrator()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest):
    logger.info("POST /chat empleado=%s mensaje=%s", payload.empleado_id, payload.mensaje)
    resultado = orquestador.responder(
        mensaje=payload.mensaje,
        empleado_id=payload.empleado_id,
    )
    return ChatResponse(respuesta=resultado["respuesta"])


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
    )