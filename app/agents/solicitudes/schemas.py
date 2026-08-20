"""Modelos de datos de entrada/salida de este agente (días, destino,
fechas, estado de la solicitud)."""

from enum import Enum

from pydantic import BaseModel


class EstadoSolicitud(str, Enum):
    PENDIENTE = "pendiente"
    APROBADA = "aprobada"
    RECHAZADA = "rechazada"


class SolicitudVacacionesInput(BaseModel):
    destino: str
    fecha_inicio: str
    fecha_fin: str


class SolicitudVacacionesResult(BaseModel):
    solicitud_id: str
    estado: EstadoSolicitud
