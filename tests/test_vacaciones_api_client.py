import pytest
import requests

from app.clients.vacaciones_api_client import VacacionesAPIClient

GUID = "3f2504e0-4f89-41d3-9a0c-0305e82c3301"


class FakeResponse:
    def __init__(self, status_code, payload, url="http://vacaciones.test"):
        self.status_code = status_code
        self._payload = payload
        self.url = url
        self.ok = 200 <= status_code < 300

    def json(self):
        return self._payload


@pytest.fixture
def cliente(monkeypatch):
    c = VacacionesAPIClient(
        base_url="http://vacaciones.test",
        use_mock=False,
        api_key="dev-key",
    )
    return c


def test_crear_solicitud_envia_contrato_y_header(monkeypatch, cliente):
    capturado = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        capturado["url"] = url
        capturado["json"] = json
        capturado["headers"] = headers
        return FakeResponse(201, {"solicitudId": GUID, "estado": "pendiente"})

    monkeypatch.setattr(requests, "post", fake_post)

    data = cliente.crear_solicitud("emp-123", "2026-09-10", "2026-09-15")

    assert capturado["url"] == "http://vacaciones.test/api/vacaciones/solicitar"
    assert capturado["json"] == {
        "empleadoId": "emp-123",
        "fechaInicio": "2026-09-10",
        "fechaFin": "2026-09-15",
    }
    assert capturado["headers"]["X-Api-Key"] == "dev-key"
    assert data["solicitud_id"] == GUID
    assert data["estado"] == "pendiente"


def test_crear_solicitud_convierte_empleado_id_numerico(monkeypatch, cliente):
    capturado = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        capturado["json"] = json
        return FakeResponse(201, {"solicitudId": GUID, "estado": "pendiente"})

    monkeypatch.setattr(requests, "post", fake_post)

    cliente.crear_solicitud(123, "2026-09-10", "2026-09-15")
    assert capturado["json"]["empleadoId"] == "123"


def test_consultar_estado_usa_guid_en_la_ruta(monkeypatch, cliente):
    capturado = {}

    def fake_get(url, headers=None, timeout=None):
        capturado["url"] = url
        capturado["headers"] = headers
        return FakeResponse(200, {"solicitudId": GUID, "estado": "aprobada"})

    monkeypatch.setattr(requests, "get", fake_get)

    data = cliente.consultar_estado(GUID)

    assert capturado["url"] == f"http://vacaciones.test/api/vacaciones/{GUID}/estado"
    assert capturado["headers"]["X-Api-Key"] == "dev-key"
    assert data["estado"] == "aprobada"


def test_consultar_estado_404_superficie_error(monkeypatch, cliente):
    def fake_get(url, headers=None, timeout=None):
        return FakeResponse(404, {"error": "Solicitud no encontrada."})

    monkeypatch.setattr(requests, "get", fake_get)

    with pytest.raises(RuntimeError) as exc:
        cliente.consultar_estado(GUID)
    assert "Solicitud no encontrada" in str(exc.value)