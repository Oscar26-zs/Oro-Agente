from app.agents.solicitudes.schemas import SolicitudOutput
from app.orchestrator.orchestrator import Orchestrator

GUID = "3f2504e0-4f89-41d3-9a0c-0305e82c3301"


class FakeSolicitudes:
    def __init__(self, estado):
        self.estado = estado

    def run(self, mensaje, empleado_id=None):
        return SolicitudOutput(
            accion="crear",
            solicitud_id=GUID,
            estado=self.estado,
            fecha_inicio="2026-09-01",
            fecha_fin="2026-09-15",
            destino="Cancun",
            mensaje="Solicitud de vacaciones creada correctamente",
        )


def test_responder_devuelve_respuesta_con_estado():
    orquestador = Orchestrator(agente_solicitudes=FakeSolicitudes("pendiente"))
    res = orquestador.responder("Quiero vacaciones a Cancun", empleado_id=123)
    assert GUID in res["respuesta"]
    assert "pendiente" in res["respuesta"]


def test_responder_con_solicitud_aprobada():
    orquestador = Orchestrator(agente_solicitudes=FakeSolicitudes("aprobada"))
    res = orquestador.responder("Quiero vacaciones a Cancun", empleado_id="123")
    assert GUID in res["respuesta"]
    assert "aprobada" in res["respuesta"]


def test_responder_con_empleado_id_como_texto():
    llamado = {}

    class CapturaSolicitudes:
        def run(self, mensaje, empleado_id=None):
            llamado["empleado_id"] = empleado_id
            return SolicitudOutput(
                accion="crear",
                solicitud_id=GUID,
                estado="pendiente",
                mensaje="Solicitud de vacaciones creada correctamente",
            )

    orquestador = Orchestrator(agente_solicitudes=CapturaSolicitudes())
    orquestador.responder("Quiero vacaciones a Cancun", empleado_id=123)
    assert llamado["empleado_id"] == "123"