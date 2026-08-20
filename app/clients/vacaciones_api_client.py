import uuid

import requests

from ..config import settings
from ..utils.logger import get_logger

logger = get_logger(__name__)


class VacacionesAPIClient:
    def __init__(
        self,
        base_url: str | None = None,
        use_mock: bool | None = None,
        api_key: str | None = None,
    ):
        self.base_url = (base_url or settings.base_url_vacaciones_api).rstrip("/")
        self.use_mock = (
            settings.use_mock_vacaciones_api if use_mock is None else use_mock
        )
        self.api_key = api_key or settings.api_key_vacaciones_api
        self._headers = {"X-Api-Key": self.api_key}

    def crear_solicitud(
        self,
        empleado_id: int | str,
        fecha_inicio: str,
        fecha_fin: str,
        destino: str | None = None,
    ) -> dict:
        if self.use_mock:
            return self._mock_crear(
                empleado_id, fecha_inicio, fecha_fin, destino
            )
        url = f"{self.base_url}/api/vacaciones/solicitar"
        payload = {
            "empleadoId": str(empleado_id),
            "fechaInicio": fecha_inicio,
            "fechaFin": fecha_fin,
        }
        data = self._post(url, payload)
        return {
            "solicitud_id": data.get("solicitudId") or data.get("solicitud_id"),
            "estado": data.get("estado", "desconocido"),
            "fecha_inicio": fecha_inicio,
            "fecha_fin": fecha_fin,
            "destino": destino,
            "mensaje": "Solicitud de vacaciones creada correctamente",
        }

    def consultar_estado(self, solicitud_id: str) -> dict:
        if self.use_mock:
            return self._mock_consultar(solicitud_id)
        url = f"{self.base_url}/api/vacaciones/{solicitud_id}/estado"
        data = self._get(url)
        return {
            "solicitud_id": solicitud_id,
            "estado": data.get("estado", "desconocido"),
            "mensaje": data.get("mensaje", "Consulta de estado realizada"),
        }

    def _post(self, url: str, payload: dict) -> dict:
        try:
            response = requests.post(url, json=payload, headers=self._headers, timeout=30)
            return self._parse(response)
        except requests.exceptions.RequestException as exc:
            logger.error("Error POST %s: %s", url, exc)
            raise RuntimeError(
                f"No se pudo crear la solicitud en el sistema de vacaciones: {exc}"
            ) from exc

    def _get(self, url: str) -> dict:
        try:
            response = requests.get(url, headers=self._headers, timeout=30)
            return self._parse(response)
        except requests.exceptions.RequestException as exc:
            logger.error("Error GET %s: %s", url, exc)
            raise RuntimeError(
                f"No se pudo consultar el estado en el sistema de vacaciones: {exc}"
            ) from exc

    @staticmethod
    def _parse(response: requests.Response) -> dict:
        if response.ok:
            return response.json()
        detalle = ""
        try:
            detalle = response.json().get("error", "")
        except ValueError:
            pass
        logger.error(
            "API vacaciones respondio %s %s: %s",
            response.status_code,
            response.url,
            detalle,
        )
        raise RuntimeError(
            f"El sistema de vacaciones respondio {response.status_code}"
            + (f": {detalle}" if detalle else "")
        )

    def _mock_crear(
        self,
        empleado_id: int | str,
        fecha_inicio: str,
        fecha_fin: str,
        destino: str | None,
    ) -> dict:
        logger.info("VacacionesAPIClient [mock] crear solicitud para empleado %s", empleado_id)
        return {
            "solicitud_id": str(uuid.uuid4()),
            "estado": "pendiente",
            "fecha_inicio": fecha_inicio,
            "fecha_fin": fecha_fin,
            "destino": destino,
            "mensaje": "Solicitud de vacaciones creada correctamente",
        }

    def _mock_consultar(self, solicitud_id: str) -> dict:
        logger.info("VacacionesAPIClient [mock] consultar estado de %s", solicitud_id)
        return {
            "solicitud_id": solicitud_id,
            "estado": "pendiente",
            "mensaje": "La solicitud esta pendiente de aprobacion",
        }