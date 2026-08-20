"""Modelos de datos del endpoint de chat: estructura del mensaje entrante
y de la respuesta que se devuelve al empleado."""

import uuid

from pydantic import BaseModel, Field, field_validator


class ChatRequest(BaseModel):
    mensaje: str = Field(..., min_length=1)
    # El sistema C# MVC usa Guid como Id de empleado en todo el dominio, no
    # un entero: este valor viaja tal cual hasta la API de vacaciones.
    empleadoId: str

    @field_validator("empleadoId")
    @classmethod
    def validar_empleado_id(cls, value: str) -> str:
        try:
            uuid.UUID(value)
        except (ValueError, AttributeError, TypeError) as exc:
            raise ValueError("empleadoId debe ser un Guid válido.") from exc
        return value


class ChatResponse(BaseModel):
    respuesta: str
