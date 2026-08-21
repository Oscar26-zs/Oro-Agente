import pytest

from app.agents.solicitudes.agent import AgenteSolicitudes
from app.agents.solicitudes.schemas import IntencionSolicitud, SolicitudOutput
from app.agents.solicitudes.tools import (
    consultar_estado_solicitud,
    crear_solicitud_vacaciones,
)

GUID = "3f2504e0-4f89-41d3-9a0c-0305e82c3301"


class FakeClient:
    def __init__(self):
        self.creadas = []

    def crear_solicitud(self, empleado_id, fecha_inicio, fecha_fin, destino=None):
        self.creadas.append(
            {
                "empleado_id": empleado_id,
                "fecha_inicio": fecha_inicio,
                "fecha_fin": fecha_fin,
                "destino": destino,
            }
        )
        return {
            "solicitud_id": GUID,
            "estado": "pendiente",
            "mensaje": "Solicitud de vacaciones creada correctamente",
        }

    def consultar_estado(self, solicitud_id):
        return {
            "solicitud_id": solicitud_id,
            "estado": "pendiente",
            "mensaje": "La solicitud esta pendiente de aprobacion",
        }


@pytest.fixture
def fake_client():
    return FakeClient()


def test_crear_solicitud_tool(fake_client):
    res = crear_solicitud_vacaciones(
        "123", "2026-09-01", "2026-09-15", "Cancun", client=fake_client
    )
    assert res["estado"] == "pendiente"
    assert res["solicitud_id"] == GUID
    assert res["destino"] == "Cancun"


def test_consultar_estado_tool(fake_client):
    res = consultar_estado_solicitud(GUID, client=fake_client)
    assert res["estado"] == "pendiente"
    assert res["solicitud_id"] == GUID


def test_agente_crea_solicitud(monkeypatch, fake_client):
    agente = AgenteSolicitudes(client=fake_client)
    monkeypatch.setattr(
        agente,
        "_analizar",
        lambda mensaje: IntencionSolicitud(
            accion="crear",
            empleado_id="123",
            fecha_inicio="2026-09-01",
            fecha_fin="2026-09-15",
            destino="Cancun",
        ),
    )
    out = agente.run(
        "Quiero vacaciones del 1 al 15 de septiembre a Cancun", empleado_id="123"
    )
    assert isinstance(out, SolicitudOutput)
    assert out.accion == "crear"
    assert out.estado == "pendiente"
    assert out.solicitud_id == GUID
    assert out.destino == "Cancun"


def test_agente_crea_solicitud_con_empleado_id_int(monkeypatch, fake_client):
    agente = AgenteSolicitudes(client=fake_client)
    monkeypatch.setattr(
        agente,
        "_analizar",
        lambda mensaje: IntencionSolicitud(
            accion="crear",
            fecha_inicio="2026-09-01",
            fecha_fin="2026-09-15",
            destino="Cancun",
        ),
    )
    out = agente.run("Quiero vacaciones a Cancun", empleado_id=123)
    assert out.estado == "pendiente"
    assert fake_client.creadas[0]["empleado_id"] == "123"


def test_agente_pide_fechas_si_faltan(monkeypatch, fake_client):
    agente = AgenteSolicitudes(client=fake_client)
    monkeypatch.setattr(
        agente,
        "_analizar",
        lambda mensaje: IntencionSolicitud(accion="crear", empleado_id="123"),
    )
    out = agente.run("Quiero vacaciones sola sin fechas", empleado_id="123")
    assert out.estado == "incompleta"
    assert "fechas" in out.mensaje.lower()


def test_agente_consulta_estado(monkeypatch, fake_client):
    agente = AgenteSolicitudes(client=fake_client)
    monkeypatch.setattr(
        agente,
        "_analizar",
        lambda mensaje: IntencionSolicitud(accion="consultar", solicitud_id=GUID),
    )
    out = agente.run(f"Como va la solicitud {GUID}", empleado_id="123")
    assert out.accion == "consultar"
    assert out.estado == "pendiente"
    assert out.solicitud_id == GUID


def test_agente_consulta_estado_error_api(monkeypatch):
    class ClientError:
        def consultar_estado(self, solicitud_id):
            raise RuntimeError("El sistema de vacaciones respondio 404: Solicitud no encontrada.")

    agente = AgenteSolicitudes(client=ClientError())
    monkeypatch.setattr(
        agente,
        "_analizar",
        lambda mensaje: IntencionSolicitud(accion="consultar", solicitud_id=GUID),
    )
    out = agente.run(f"Como va la solicitud {GUID}", empleado_id="123")
    assert out.estado == "error"
    assert "no existe" in out.mensaje
    assert GUID in out.mensaje


def test_agente_consulta_estado_error_generico(monkeypatch):
    class ClientError500:
        def consultar_estado(self, solicitud_id):
            raise RuntimeError("El sistema de vacaciones respondio 500")

    agente = AgenteSolicitudes(client=ClientError500())
    monkeypatch.setattr(
        agente,
        "_analizar",
        lambda mensaje: IntencionSolicitud(accion="consultar", solicitud_id=GUID),
    )
    out = agente.run(f"Como va la solicitud {GUID}", empleado_id="123")
    assert out.estado == "error"
    assert "500" in out.mensaje
    assert "no existe" not in out.mensaje


def test_heuristica_captura_guid_y_empleado_a_str():
    agente = AgenteSolicitudes(client=FakeClient())
    intencion = agente._heuristica(
        f"quiero consultar el estado de la solicitud {GUID}"
    )
    assert intencion.accion == "consultar"
    assert intencion.solicitud_id == GUID


def test_heuristica_consultar_sin_id():
    agente = AgenteSolicitudes(client=FakeClient())
    intencion = agente._heuristica("como va mi solicitud")
    assert intencion.accion == "consultar"
    assert intencion.solicitud_id is None


# ------------------------------------------------------------------ ayuda

def test_heuristica_saludo_devuelve_ayuda():
    agente = AgenteSolicitudes(client=FakeClient())
    assert agente._heuristica("hola que tal").accion == "ayuda"
    assert agente._heuristica("gracias por todo").accion == "ayuda"


class _Respuesta:
    def __init__(self, content):
        self.content = content


class _ModeloFijo:
    def __init__(self, content):
        self._content = content

    def generate(self, mensajes):
        return _Respuesta(self._content)


def test_analisis_con_accion_desconocida_cae_en_ayuda():
    agente = AgenteSolicitudes(client=FakeClient())
    agente._model = _ModeloFijo('{"accion": "cualquiercosa"}')
    intencion = agente._analizar("hola")
    assert intencion.accion == "ayuda"


def test_analisis_estado_sin_guid_devuelve_consultar():
    agente = AgenteSolicitudes(client=FakeClient())
    agente._model = _ModeloFijo(
        '{"accion": "consultar", "solicitud_id": null, "empleado_id": null, '
        '"fecha_inicio": null, "fecha_fin": null, "destino": null}'
    )
    out = agente.run("como va mi solicitud?", empleado_id="123")
    assert out.estado != "incompleta"  # nunca pide fechas por una consulta


def test_agente_responde_menu_en_saludos(monkeypatch):
    agente = AgenteSolicitudes(client=FakeClient())
    monkeypatch.setattr(
        agente,
        "_analizar",
        lambda mensaje: IntencionSolicitud(accion="ayuda"),
    )
    out = agente.run("hola", empleado_id="123")
    assert out.estado != "incompleta"
    texto = out.mensaje.lower()
    assert "solicitar vacaciones" in texto
    assert "identificador" in texto


# ------------------------------------------------- consultar sin identificador

class StoreFijo:
    def __init__(self, viaje=None):
        self._viaje = viaje

    def ultimo_viaje_de_empleado(self, empleado_id):
        if self._viaje is None:
            return None
        return dict(self._viaje)


def test_consulta_sin_guid_usa_ultimo_viaje_del_store(monkeypatch):
    agente = AgenteSolicitudes(
        client=FakeClient(),
        store=StoreFijo({"solicitud_id": GUID}),
    )
    monkeypatch.setattr(
        agente,
        "_analizar",
        lambda mensaje: IntencionSolicitud(accion="consultar"),
    )
    out = agente.run("como va mi solicitud?", empleado_id="123")
    assert out.solicitud_id == GUID
    assert out.estado == "pendiente"


def test_consulta_sin_guid_y_sin_registro_pide_identificador(monkeypatch):
    agente = AgenteSolicitudes(client=FakeClient(), store=StoreFijo(None))
    monkeypatch.setattr(
        agente,
        "_analizar",
        lambda mensaje: IntencionSolicitud(accion="consultar"),
    )
    out = agente.run("como va mi solicitud?", empleado_id="123")
    assert out.estado == "informativo"
    assert "identificador" in out.mensaje.lower()
    # preguntar por el estado JAMAS pide fechas de una creacion
    assert "necesito que me indiques el destino" not in out.mensaje


# ------------------------------------------------------------------ plan

def test_heuristica_peticion_plan_devuelve_accion_plan():
    agente = AgenteSolicitudes(client=FakeClient())
    assert agente._heuristica("quiero mi plan de viaje").accion == "plan"
    assert agente._heuristica("creame el viaje a cancun").accion == "plan"
    assert agente._heuristica("que hoteles hay por alla").accion == "plan"


def test_creacion_con_fechas_gana_sobre_palabras_de_plan():
    agente = AgenteSolicitudes(client=FakeClient())
    intencion = agente._heuristica(
        "quiero vacaciones del 01/09/2026 al 15/09/2026, sera un buen viaje"
    )
    assert intencion.accion == "crear"
    assert intencion.fecha_inicio == "2026-09-01"


def test_analisis_plan_del_modelo_entrega_salida_vacia():
    agente = AgenteSolicitudes(client=FakeClient())
    agente._model = _ModeloFijo(
        '{"accion": "plan", "solicitud_id": null, "empleado_id": null, '
        '"fecha_inicio": null, "fecha_fin": null, "destino": "Cancun"}'
    )
    out = agente.run("quiero mi plan de viaje", empleado_id="123")
    assert out.accion == "plan"
    assert out.mensaje == ""