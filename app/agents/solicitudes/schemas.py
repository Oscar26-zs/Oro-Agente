from pydantic import BaseModel, Field


class SolicitudInput(BaseModel):
    empleado_id: str | None = None
    mensaje: str


class IntencionSolicitud(BaseModel):
    accion: str = "consultar"
    solicitud_id: str | None = None
    empleado_id: str | None = None
    fecha_inicio: str | None = None
    fecha_fin: str | None = None
    destino: str | None = None


class SolicitudOutput(BaseModel):
    accion: str
    solicitud_id: str | None = None
    estado: str = "desconocido"
    fecha_inicio: str | None = None
    fecha_fin: str | None = None
    destino: str | None = None
    mensaje: str = ""


class SolicitudCrearOutput(SolicitudOutput):
    pass


class SolicitudConsultarOutput(SolicitudOutput):
    pass