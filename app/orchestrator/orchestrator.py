from ..agents.solicitudes.agent import AgenteSolicitudes
from ..agents.solicitudes.schemas import SolicitudOutput
from ..utils.logger import get_logger

logger = get_logger(__name__)


class Orchestrator:
    def __init__(
        self,
        agente_solicitudes: AgenteSolicitudes | None = None,
    ):
        self.solicitudes = agente_solicitudes or AgenteSolicitudes()

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
        return {"respuesta": self._texto(resultado)}

    def _texto(self, resultado: SolicitudOutput) -> str:
        if resultado.estado.lower() == "incompleta":
            return resultado.mensaje
        if resultado.solicitud_id:
            return (
                f"{resultado.mensaje} Solicitud #{resultado.solicitud_id} "
                f"con estado {resultado.estado}."
            )
        return resultado.mensaje or f"Su solicitud quedo en estado {resultado.estado}."