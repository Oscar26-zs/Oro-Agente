from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    mensaje: str = Field(..., min_length=1)
    empleado_id: str | None = Field(default=None, alias="empleadoId")

    model_config = {"populate_by_name": True}


class ChatResponse(BaseModel):
    respuesta: str