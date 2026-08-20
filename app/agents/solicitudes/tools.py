"""Funciones que el agente usa como herramientas: crear solicitud y
consultar estado, llamando al cliente HTTP de la API externa."""

import json

from smolagents import tool

from app.clients.vacaciones_api_client import VacacionesApiClient, VacacionesApiError

_client = VacacionesApiClient()


@tool
def crear_solicitud_vacaciones(empleado_id: str, destino: str, fecha_inicio: str, fecha_fin: str) -> str:
    """Crea una solicitud de vacaciones para un empleado en el sistema de RRHH (C# MVC),
    vía POST a /api/vacaciones/solicitar.

    Args:
        empleado_id: Id del empleado que solicita las vacaciones (un Guid en formato
            texto, ej. '2c2a9142-4f21-4e46-8b70-a998f6e3cd32'). Usa siempre el
            empleadoId indicado en la tarea que recibiste, nunca inventes otro.
        destino: Destino del viaje, ej. 'Panamá'.
        fecha_inicio: Fecha de inicio en formato YYYY-MM-DD.
        fecha_fin: Fecha de fin en formato YYYY-MM-DD.
    """
    try:
        resultado = _client.crear_solicitud(empleado_id, destino, fecha_inicio, fecha_fin)
    except VacacionesApiError as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False)

    return json.dumps(resultado, ensure_ascii=False)


@tool
def consultar_estado_solicitud(solicitud_id: str) -> str:
    """Consulta el estado actual de una solicitud de vacaciones en el sistema de RRHH
    (C# MVC), vía GET a /api/vacaciones/{solicitud_id}/estado.

    Args:
        solicitud_id: Id de la solicitud a consultar (un Guid en formato texto, el
            mismo que devolvió crear_solicitud_vacaciones).
    """
    try:
        resultado = _client.consultar_estado(solicitud_id)
    except VacacionesApiError as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False)

    return json.dumps(resultado, ensure_ascii=False)
