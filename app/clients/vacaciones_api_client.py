"""Cliente HTTP que consume la API REST del sistema de vacaciones (otro
repositorio, C# MVC). No implementa esa API, solo la consume."""

import requests

from app.config import VACACIONES_API_KEY, VACACIONES_API_URL


class VacacionesApiError(Exception):
    """Error al comunicarse con la API del sistema de vacaciones."""


class VacacionesApiClient:
    def __init__(self, base_url: str | None = None, api_key: str | None = None, timeout: int = 10):
        self.base_url = (base_url or VACACIONES_API_URL).rstrip("/")
        self.api_key = api_key if api_key is not None else VACACIONES_API_KEY
        self.timeout = timeout

    def crear_solicitud(self, empleado_id: str, destino: str, fecha_inicio: str, fecha_fin: str) -> dict:
        url = f"{self.base_url}/api/vacaciones/solicitar"
        payload = {
            "empleadoId": empleado_id,
            "destino": destino,
            "fechaInicio": fecha_inicio,
            "fechaFin": fecha_fin,
        }
        return self._request("POST", url, json=payload)

    def consultar_estado(self, solicitud_id: str) -> dict:
        url = f"{self.base_url}/api/vacaciones/{solicitud_id}/estado"
        return self._request("GET", url)

    def _request(self, method: str, url: str, **kwargs) -> dict:
        # El endpoint C# exige el header X-Api-Key (ApiKeyAuthFilter): sin él,
        # o con la key equivocada, responde 401; si el servidor no tiene la
        # key configurada del lado suyo, responde 503.
        headers = {"X-Api-Key": self.api_key} if self.api_key else {}

        try:
            response = requests.request(method, url, timeout=self.timeout, headers=headers, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.ConnectionError as exc:
            raise VacacionesApiError(
                "No se pudo conectar con el sistema de vacaciones. Verifique que esté disponible."
            ) from exc
        except requests.exceptions.Timeout as exc:
            raise VacacionesApiError("El sistema de vacaciones tardó demasiado en responder.") from exc
        except requests.exceptions.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            if status == 404:
                raise VacacionesApiError("No se encontró la solicitud indicada.") from exc
            if status == 401:
                raise VacacionesApiError(
                    "El sistema de vacaciones rechazó la API key (401). Verifique VACACIONES_API_KEY."
                ) from exc
            if status == 503:
                raise VacacionesApiError(
                    "El sistema de vacaciones no tiene su API key configurada del lado del servidor (503)."
                ) from exc
            raise VacacionesApiError(f"El sistema de vacaciones respondió con un error: {exc}") from exc
        except ValueError as exc:
            raise VacacionesApiError("El sistema de vacaciones devolvió una respuesta inválida.") from exc
