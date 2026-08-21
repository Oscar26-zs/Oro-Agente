from pydantic import BaseModel


class ViajeInput(BaseModel):
    destino: str
    fecha_inicio: str | None = None
    fecha_fin: str | None = None
    mensaje: str = ""


class ViajeOutput(BaseModel):
    destino: str
    fecha_inicio: str | None = None
    fecha_fin: str | None = None
    recomendaciones: str = ""
    mensaje: str = ""
