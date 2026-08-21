from ..agents.solicitudes.agent import AgenteSolicitudes
from ..agents.solicitudes.schemas import SolicitudOutput
from ..agents.viajes.agent import AgenteViaje
from ..clients.vacaciones_api_client import VacacionesAPIClient
from ..store.viajes_store import ViajesStore
from ..utils.logger import get_logger

logger = get_logger(__name__)

ESTADO_APROBADO = "aprobada"
ESTADO_PENDIENTE = "pendiente"
ESTADOS_SIN_VIAJE = {"error", "incompleta"}

PLAN_KEYWORDS = (
    "plan",
    "viaje",
    "viajar",
    "vuelo",
    "hotel",
    "actividade",
    "recomend",
    "itinerario",
    "que hacer",
    "que visitar",
    "preparame",
    "muestrame",
    "armame",
    "si quiero",
    "dale",
    "hazlo",
    "obvio",
)

OFERTA_PLAN = (
    'Si quieres, te preparo tu plan de viaje: escribe "quiero mi plan de viaje" '
    "y te comparto clima, vuelos, hoteles y actividades."
)


def _solicitud_inexistente(exc: Exception) -> bool:
    texto = str(exc)
    return "404" in texto or "no encontrada" in texto.lower()


def _pide_plan(mensaje: str) -> bool:
    """True si el mensaje del empleado pide explicitamente su plan de viaje."""
    texto = (mensaje or "").lower()
    return any(k in texto for k in PLAN_KEYWORDS)


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
        self.viajes = agente_viaje or AgenteViaje()
        self.store = store if store is not None else ViajesStore()
        self.solicitudes = (
            agente_solicitudes if agente_solicitudes is not None else AgenteSolicitudes()
        )
        # El agente de solicitudes comparte el mismo contexto del orquestador.
        if hasattr(self.solicitudes, "store"):
            self.solicitudes.store = self.store
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

        partes = []
        if resultado.accion != "plan":
            partes.append(self._texto(resultado))
            oferta = self._oferta_si_aprobada(resultado)
            if oferta:
                partes.append(oferta)
        plan = self._entregar_si_piden_plan(
            empleado, mensaje, pedir_plan=resultado.accion == "plan"
        )
        if plan:
            partes.append(plan)
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

    def _entregar_si_piden_plan(
        self,
        empleado: str | None,
        mensaje: str,
        pedir_plan: bool = False,
    ) -> str | None:
        """Entrega recomendaciones SOLO cuando el empleado pide su plan.

        La senal puede venir del clasificador del Agente 1 (pedir_plan=True)
        o de las palabras clave del mensaje como respaldo. Preguntar por el
        estado o saludar nunca activa al agente de viaje. El plan se entrega
        UNA sola vez: si ya se entrego, se avisa en lugar de repetirlo.
        """
        if not empleado or not (pedir_plan or _pide_plan(mensaje)):
            return None
        try:
            pendientes = self.store.viajes_pendientes_de_empleado(empleado)
            if not pendientes:
                return self._aviso_sin_plan_nuevo(empleado)
        except Exception as exc:
            logger.warning("Store de viajes no disponible: %s", exc)
            return None

        bloques = []
        notas = []
        for viaje in pendientes:
            sid = viaje.get("solicitud_id")
            estado_info, retirar = self._consultar_estado(sid)
            if retirar:
                try:
                    self.store.eliminar(sid)
                    logger.info(
                        "Se retiro del contexto la solicitud inexistente %s", sid
                    )
                except Exception as exc:
                    logger.warning("No se pudo actualizar el store: %s", exc)
                continue
            if estado_info is None:
                continue
            estado = str(estado_info.get("estado", "")).lower()
            if estado == ESTADO_APROBADO:
                bloque = self._bloque_aprobacion(viaje, mensaje)
                if bloque is None:
                    continue
                try:
                    self.store.marcar_entregado(sid)
                except Exception as exc:
                    logger.warning("No se pudo actualizar el store: %s", exc)
                bloques.append(bloque)
            elif estado == ESTADO_PENDIENTE:
                notas.append(
                    f"Tu solicitud {sid} sigue pendiente de aprobacion; en cuanto "
                    "se apruebe te preparo el plan de viaje."
                )
            else:
                notas.append(f"Tu solicitud {sid} figura con estado {estado}.")
        partes = bloques + notas
        return " ".join(partes) if partes else None

    def _aviso_sin_plan_nuevo(self, empleado: str) -> str | None:
        """Mensaje cuando piden el plan pero no queda nada por entregar."""
        try:
            historial = self.store.viajes_de_empleado(empleado)
        except Exception as exc:
            logger.warning("Store de viajes no disponible: %s", exc)
            return None
        if any(v.get("recomendaciones_entregadas") for v in historial):
            return (
                "Ya te entregue tu plan de viaje. Si necesitas consultarlo de "
                "nuevo o algo cambio en tu solicitud, dimelo y lo revisamos."
            )
        return (
            "No tengo registro de una solicitud tuya en esta conversacion. Crea "
            "una indicando fechas y destino, o pasame el identificador (GUID) "
            "si ya existe."
        )

    def _consultar_estado(self, solicitud_id) -> tuple[dict | None, bool]:
        """Consulta el estado de una solicitud del contexto.

        Retorna (info, retirar): retirar=True cuando la solicitud ya no existe
        en el sistema (404) y debe salir del contexto para no volver a
        consultarse.
        """
        try:
            return self._cliente_estado.consultar_estado(solicitud_id), False
        except Exception as exc:
            if _solicitud_inexistente(exc):
                return None, True
            logger.warning(
                "No se pudo consultar el estado de %s: %s", solicitud_id, exc
            )
            return None, False

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
        if resultado.estado.lower() == "error":
            return resultado.mensaje or "Su solicitud quedo en estado error."
        if resultado.solicitud_id:
            return (
                f"{resultado.mensaje} Solicitud #{resultado.solicitud_id} "
                f"con estado {resultado.estado}."
            )
        return resultado.mensaje or f"Su solicitud quedo en estado {resultado.estado}."

    # ------------------------------------------------------------------
    # Textos de respuesta

    @staticmethod
    def _oferta_si_aprobada(resultado: SolicitudOutput) -> str | None:
        """Ofrece el plan de viaje cuando una solicitud sale aprobada.

        Nunca entrega el plan de inmediato: se espera el pedido del empleado.
        """
        if resultado.estado.lower() != ESTADO_APROBADO:
            return None
        return OFERTA_PLAN
