"""Coordina agente_solicitudes y agente_viaje aplicando la regla de negocio
(solo se investiga el viaje si la solicitud está "aprobada") con lógica
determinística en Python, sin gastar llamadas LLM en un orquestador: cada
mensaje solo consume tokens en los agentes especialistas."""

from app.agents.solicitudes.agent import crear_agente_solicitudes
from app.agents.viaje.agent import buscar_info_viaje
from app.agents.viaje.tools import parsear_json_respuesta
from app.utils.logger import get_logger

logger = get_logger(__name__)

MENSAJE_ERROR_INTERNO = (
    "Recibí tu mensaje, pero tuve un problema al procesarlo. "
    "Intenta de nuevo en unos momentos."
)


def debe_investigar_viaje(estado: str) -> bool:
    """Regla de negocio: solo se investiga el viaje si la solicitud fue aprobada."""
    return estado == "aprobada"


def _a_texto(valor) -> str:
    """Convierte un campo del JSON del agente_viaje en texto legible."""
    if isinstance(valor, list) and valor:
        return "; ".join(str(v) for v in valor)
    if isinstance(valor, str) and valor.strip():
        return valor.strip()
    return "No se encontró información."


def componer_respuesta_aprobada(info: dict, destino: str, fecha_inicio: str, fecha_fin: str) -> str:
    """Arma la respuesta final para el empleado sin llamar al modelo otra vez."""
    return "\n".join([
        f"¡Tu solicitud fue aprobada! Información para tu viaje a {destino}, "
        f"del {fecha_inicio} al {fecha_fin}:",
        "",
        f"Vuelos: {_a_texto(info.get('vuelos'))}",
        f"Hoteles: {_a_texto(info.get('hoteles'))}",
        f"Clima: {_a_texto(info.get('clima'))}",
        f"Actividades: {_a_texto(info.get('actividades'))}",
    ])


def procesar_mensaje(mensaje: str, empleado_id: str) -> str:
    agente_solicitudes = crear_agente_solicitudes(empleado_id)

    try:
        resultado = agente_solicitudes.run(
            f'Mensaje del empleado (empleadoId={empleado_id}): "{mensaje}"'
        )
        datos = parsear_json_respuesta(str(resultado))
    except Exception:
        logger.exception(
            "agente_solicitudes falló o devolvió algo que no es JSON (empleadoId=%s)",
            empleado_id,
        )
        return MENSAJE_ERROR_INTERNO

    if datos.get("error"):
        return datos.get("mensaje") or MENSAJE_ERROR_INTERNO

    estado = datos.get("estado")
    if not debe_investigar_viaje(estado):
        return datos.get("mensaje") or (
            "Tu solicitud quedó registrada y está pendiente de aprobación."
        )

    destino = datos.get("destino")
    fecha_inicio = datos.get("fecha_inicio")
    fecha_fin = datos.get("fecha_fin")
    if not (destino and fecha_inicio and fecha_fin):
        return (datos.get("mensaje") or "") + (
            " Para investigar vuelos, hoteles y clima necesito el destino y las fechas del viaje."
        )

    try:
        info = buscar_info_viaje(str(destino), str(fecha_inicio), str(fecha_fin))
    except Exception:
        logger.exception("agente_viaje falló (empleadoId=%s)", empleado_id)
        return (datos.get("mensaje") or "") + (
            " No pude investigar la información del viaje en este momento."
        )

    return componer_respuesta_aprobada(info, str(destino), str(fecha_inicio), str(fecha_fin))
