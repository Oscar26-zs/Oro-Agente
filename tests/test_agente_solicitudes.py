"""Pruebas del agente de solicitudes y su interacción con la API externa."""

from unittest.mock import patch

import pytest
import requests

from app.agents.solicitudes import tools
from app.clients.vacaciones_api_client import VacacionesApiClient, VacacionesApiError

EMPLEADO_ID = "2c2a9142-4f21-4e46-8b70-a998f6e3cd32"
SOLICITUD_ID = "9b9a73a2-c629-4385-b581-cd7d290b5f8c"


def test_crear_solicitud_construye_payload_correcto():
    client = VacacionesApiClient(base_url="http://localhost:5051", api_key="clave-de-prueba")
    with patch("requests.request") as mock_request:
        mock_request.return_value.raise_for_status = lambda: None
        mock_request.return_value.json.return_value = {"solicitudId": SOLICITUD_ID, "estado": "pendiente"}

        resultado = client.crear_solicitud(EMPLEADO_ID, "Panamá", "2026-09-10", "2026-09-15")

    assert resultado == {"solicitudId": SOLICITUD_ID, "estado": "pendiente"}
    _, kwargs = mock_request.call_args
    assert kwargs["json"] == {
        "empleadoId": EMPLEADO_ID,
        "destino": "Panamá",
        "fechaInicio": "2026-09-10",
        "fechaFin": "2026-09-15",
    }
    assert kwargs["headers"] == {"X-Api-Key": "clave-de-prueba"}


def test_crear_solicitud_sin_api_key_no_envia_el_header():
    client = VacacionesApiClient(base_url="http://localhost:5051", api_key=None)
    with patch("requests.request") as mock_request:
        mock_request.return_value.raise_for_status = lambda: None
        mock_request.return_value.json.return_value = {"solicitudId": SOLICITUD_ID, "estado": "pendiente"}

        client.crear_solicitud(EMPLEADO_ID, "Panamá", "2026-09-10", "2026-09-15")

    _, kwargs = mock_request.call_args
    assert kwargs["headers"] == {}


def test_consultar_estado_propaga_error_de_conexion():
    client = VacacionesApiClient(base_url="http://localhost:5051")
    with patch("requests.request", side_effect=requests.exceptions.ConnectionError()):
        with pytest.raises(VacacionesApiError):
            client.consultar_estado(SOLICITUD_ID)


def test_crear_solicitud_vacaciones_tool_devuelve_json_de_la_api():
    with patch.object(
        tools._client, "crear_solicitud", return_value={"solicitudId": SOLICITUD_ID, "estado": "pendiente"}
    ) as mock_crear:
        salida = tools.crear_solicitud_vacaciones(
            empleado_id=EMPLEADO_ID, destino="Panamá", fecha_inicio="2026-09-10", fecha_fin="2026-09-15"
        )

    mock_crear.assert_called_once_with(EMPLEADO_ID, "Panamá", "2026-09-10", "2026-09-15")
    assert SOLICITUD_ID in salida
    assert "pendiente" in salida


def test_crear_solicitud_vacaciones_tool_devuelve_error_si_falla_la_api():
    with patch.object(tools._client, "crear_solicitud", side_effect=VacacionesApiError("sin conexión")):
        salida = tools.crear_solicitud_vacaciones(
            empleado_id=EMPLEADO_ID, destino="Panamá", fecha_inicio="2026-09-10", fecha_fin="2026-09-15"
        )

    assert "error" in salida
    assert "sin conexión" in salida


def test_consultar_estado_solicitud_tool_devuelve_json_de_la_api():
    with patch.object(
        tools._client, "consultar_estado", return_value={"solicitudId": SOLICITUD_ID, "estado": "aprobada"}
    ) as mock_consultar:
        salida = tools.consultar_estado_solicitud(solicitud_id=SOLICITUD_ID)

    mock_consultar.assert_called_once_with(SOLICITUD_ID)
    assert "aprobada" in salida


def test_consultar_estado_solicitud_tool_devuelve_error_si_falla_la_api():
    with patch.object(tools._client, "consultar_estado", side_effect=VacacionesApiError("no encontrada")):
        salida = tools.consultar_estado_solicitud(solicitud_id=SOLICITUD_ID)

    assert "error" in salida
    assert "no encontrada" in salida
