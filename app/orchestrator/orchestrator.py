from ..agents.solicitudes.agent import AgenteSolicitudes
from ..agents.solicitudes.schemas import SolicitudOutput
from ..agents.viajes.agent import AgenteViaje
from ..utils.logger import get_logger

logger = get_logger(__name__)

ESTADO_APROBADO = "aprobada"


class Orchestrator:
    def __init__(
        self,
        agente_solicitudes: AgenteSolicitudes | None = None,
        agente_viaje: AgenteViaje | None = None,
    ):
        self.solicitudes = agente_solicitudes or AgenteSolicitudes()
        self.viajes = agente_viaje or AgenteViaje()

    def responder(
        self,
        mensaje: str,
        empleado_id: int | str | None = None,
    ) -> dict:
        logger.info("Orquestador recibe mensaje de empleado %s", empleado_id)
        resultado = self.solicitudes.run(
            mensaje,
            empleado_id=str(empleado_id) if empleado_id is not None else None,
        )
        logger.info(
            "Agente de solicitudes: accion=%s estado=%s solicitud=%s",
            resultado.accion,
            resultado.estado,
            resultado.solicitud_id,
        )
        texto = self._texto(resultado)
        texto_viaje = self._texto_viaje(resultado, mensaje)
        if texto_viaje:
            texto = f"{texto} {texto_viaje}"
        return {"respuesta": texto}

    def _texto(self, resultado: SolicitudOutput) -> str:
        if resultado.estado.lower() == "incompleta":
            return resultado.mensaje
        if resultado.solicitud_id:
            return (
                f"{resultado.mensaje} Solicitud #{resultado.solicitud_id} "
                f"con estado {resultado.estado}."
            )
        return resultado.mensaje or f"Su solicitud quedo en estado {resultado.estado}."

    def _texto_viaje(self, resultado: SolicitudOutput, mensaje: str) -> str | None:
        if resultado.estado.lower() != ESTADO_APROBADO:
            return None
        if not resultado.destino:
            logger.info(
                "Solicitud aprobada sin destino; no se activa el agente de viaje"
            )
            return None
        try:
            viaje = self.viajes.run(
                destino=resultado.destino,
                fecha_inicio=resultado.fecha_inicio,
                fecha_fin=resultado.fecha_fin,
                mensaje=mensaje,
            )
            logger.info("Agente de viaje genero recomendaciones para %s", viaje.destino)
            return viaje.recomendaciones
        except Exception as exc:
            logger.warning("Agente de viaje fallo (%s); se omite su seccion", exc)
            return None
