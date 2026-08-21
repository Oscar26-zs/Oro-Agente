from ..agents.solicitudes.agent import AgenteSolicitudes
from ..agents.solicitudes.schemas import SolicitudOutput
from ..agents.viajes.agent import AgenteViaje
from ..clients.vacaciones_api_client import VacacionesAPIClient
from ..store.viajes_store import ViajesStore
from ..utils.logger import get_logger

logger = get_logger(__name__)

ESTADO_APROBADO = "aprobada"
ESTADOS_SIN_VIAJE = {"error", "incompleta"}


class Orchestrator:
    """Coordina los agentes y mantiene el contexto de conversacion.

    El contexto vive en un ViajesStore: cuando el Agente 1 crea una solicitud,
    se recuerda {solicitud_id -> empleado, destino, fechas}. En cualquier mensaje
    posterior del empleado, si esa solicitud aparece aprobada, se usa ese contexto
    guardado para pedirle al Agente 2 las recomendaciones de viaje.
    """

    def __init__(
        self,
        agente_solicitudes: AgenteSolicitudes | None = None,
        agente_viaje: AgenteViaje | None = None,
        store: ViajesStore | None = None,
        cliente_estado=None,
    ):
        self.solicitudes = agente_solicitudes or AgenteSolicitudes()
        self.viajes = agente_viaje or AgenteViaje()
        self.store = store if store is not None else ViajesStore()
        self._cliente_estado_inyectado = cliente_estado

    @property
    def _cliente_estado(self):
        if self._cliente_estado_inyectado is None:
            self._cliente_estado_inyectado = (
                getattr(self.solicitudes, "client", None) or VacacionesAPIClient()
            )
        return self._cliente_estado_inyectado

    def responder(
        self,
        mensaje: str,
        empleado_id: int | str | None = None,
    ) -> dict:
        logger.info("Orquestador recibe mensaje de empleado %s", empleado_id)
        empleado = str(empleado_id) if empleado_id is not None else None

        resultado = self.solicitudes.run(mensaje, empleado_id=empleado)
        logger.info(
            "Agente de solicitudes: accion=%s estado=%s solicitud=%s",
            resultado.accion,
            resultado.estado,
            resultado.solicitud_id,
        )

        self._registrar_viaje(resultado, empleado)

        partes = [self._texto(resultado)]
        texto_mismo_turno = self._texto_viaje(resultado, mensaje)
        if texto_mismo_turno:
            partes.append(texto_mismo_turno)
        texto_contexto = self._revisar_aprobaciones_previas(empleado, mensaje)
        if texto_contexto:
            partes.append(texto_contexto)
        return {"respuesta": " ".join(p for p in partes if p)}

    # ------------------------------------------------------------------
    # Contexto de conversacion (memoria del orquestador)

    def _registrar_viaje(
        self, resultado: SolicitudOutput, empleado: str | None
    ) -> None:
        """Guarda el contexto de la solicitud recien creada o consultada."""
        if resultado.estado.lower() in ESTADOS_SIN_VIAJE:
            return
        if not resultado.solicitud_id:
            return
        try:
            self.store.guardar_viaje(
                solicitud_id=resultado.solicitud_id,
                empleado_id=empleado,
                destino=resultado.destino,
                fecha_inicio=resultado.fecha_inicio,
                fecha_fin=resultado.fecha_fin,
            )
        except Exception as exc:
            logger.warning("No se pudo guardar el contexto del viaje: %s", exc)

    def _revisar_aprobaciones_previas(
        self, empleado: str | None, mensaje: str
    ) -> str | None:
        """Detecta solicitudes previas que pasaron a aprobada y entrega su bloque."""
        if not empleado:
            return None
        try:
            pendientes = self.store.viajes_pendientes_de_empleado(empleado)
        except Exception as exc:
            logger.warning("Store de viajes no disponible: %s", exc)
            return None
        if not pendientes:
            return None

        bloques = []
        for viaje in pendientes:
            sid = viaje.get("solicitud_id")
            estado_info = self._estado_seguro(sid)
            if estado_info is None:
                continue
            if str(estado_info.get("estado", "")).lower() != ESTADO_APROBADO:
                continue
            bloque = self._bloque_aprobacion(viaje, mensaje)
            if bloque is None:
                continue
            try:
                self.store.marcar_entregado(sid)
            except Exception as exc:
                logger.warning("No se pudo actualizar el store: %s", exc)
            bloques.append(bloque)
        return " ".join(bloques) if bloques else None

    def _estado_seguro(self, solicitud_id) -> dict | None:
        try:
            return self._cliente_estado.consultar_estado(solicitud_id)
        except Exception as exc:
            logger.warning(
                "No se pudo consultar el estado de %s: %s", solicitud_id, exc
            )
            return None

    def _bloque_aprobacion(self, viaje: dict, mensaje: str) -> str | None:
        """Texto de felicitacion + recomendaciones usando el contexto guardado."""
        encabezado = (
            "Buenas noticias: tu solicitud fue APROBADA en el sistema de vacaciones."
        )
        destino = viaje.get("destino")
        if not destino:
            return (
                f"{encabezado} Para donde quieres viajar? Contame el destino y te "
                "preparo ideas de vuelos, hoteles y actividades."
            )
        try:
            salida = self.viajes.run(
                destino=destino,
                fecha_inicio=viaje.get("fecha_inicio"),
                fecha_fin=viaje.get("fecha_fin"),
                mensaje=mensaje,
            )
        except Exception as exc:
            logger.warning("Agente de viaje fallo (%s); se reintenta luego", exc)
            return None
        return f"{encabezado} {salida.recomendaciones}"

    # ------------------------------------------------------------------
    # Textos de respuesta

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
        """Disparador de mismo turno: la creacion devolvio aprobada directamente."""
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
        except Exception as exc:
            logger.warning("Agente de viaje fallo (%s); se omite su seccion", exc)
            return None
        if resultado.solicitud_id:
            try:
                self.store.marcar_entregado(resultado.solicitud_id)
            except Exception as exc:
                logger.warning("No se pudo actualizar el store: %s", exc)
        logger.info("Agente de viaje genero recomendaciones para %s", viaje.destino)
        return viaje.recomendaciones
