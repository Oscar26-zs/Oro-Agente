from ...clients.vacaciones_api_client import VacacionesAPIClient

_default_client: VacacionesAPIClient | None = None


def _client() -> VacacionesAPIClient:
    global _default_client
    if _default_client is None:
        _default_client = VacacionesAPIClient()
    return _default_client


def set_default_client(client: VacacionesAPIClient | None) -> None:
    global _default_client
    _default_client = client


def crear_solicitud_vacaciones(
    empleado_id: int | str,
    fecha_inicio: str,
    fecha_fin: str,
    destino: str | None = None,
    client: VacacionesAPIClient | None = None,
) -> dict:
    c = client or _client()
    data = c.crear_solicitud(
        empleado_id=empleado_id,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        destino=destino,
    )
    data.setdefault("fecha_inicio", fecha_inicio)
    data.setdefault("fecha_fin", fecha_fin)
    data.setdefault("destino", destino)
    data.setdefault("estado", "desconocido")
    return data


def consultar_estado_solicitud(
    solicitud_id: str,
    client: VacacionesAPIClient | None = None,
) -> dict:
    c = client or _client()
    data = c.consultar_estado(solicitud_id=solicitud_id)
    data.setdefault("solicitud_id", solicitud_id)
    data.setdefault("estado", "desconocido")
    return data