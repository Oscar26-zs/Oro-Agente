"""Modelos de datos de entrada/salida de este agente (destino, fechas,
clima, vuelos, hoteles, actividades)."""

from pydantic import BaseModel


class InfoViajeInput(BaseModel):
    destino: str
    fecha_inicio: str
    fecha_fin: str


class InfoViajeResult(BaseModel):
    vuelos: list[str]
    hoteles: list[str]
    clima: str
    actividades: list[str]
