from app.agents.solicitudes.schemas import SolicitudOutput
from app.agents.viajes.schemas import ViajeOutput
from app.orchestrator.orchestrator import Orchestrator

GUID = "3f2504e0-4f89-41d3-9a0c-0305e82c3301"


class FakeSolicitudes:
    def __init__(self, estado, destino="Cancun"):
        self.estado = estado
        self.destino = destino

    def run(self, mensaje, empleado_id=None):
        return SolicitudOutput(
            accion="crear",
            solicitud_id=GUID,
            estado=self.estado,
            fecha_inicio="2026-09-01",
            fecha_fin="2026-09-15",
            destino=self.destino,
            mensaje="Solicitud de vacaciones creada correctamente",
        )


class FakeViajes:
    def __init__(self):
        self.llamados = []

    def run(self, destino, fecha_inicio=None, fecha_fin=None, mensaje=""):
        self.llamados.append(
            {
                "destino": destino,
                "fecha_inicio": fecha_inicio,
                "fecha_fin": fecha_fin,
                "mensaje": mensaje,
            }
        )
        return ViajeOutput(
            destino=destino,
            recomendaciones=f"Ideas de viaje para {destino}: playa y tour cultural.",
        )


def test_responder_devuelve_respuesta_con_estado():
    orquestador = Orchestrator(
        agente_solicitudes=FakeSolicitudes("pendiente"), agente_viaje=FakeViajes()
    )
    res = orquestador.responder("Quiero vacaciones a Cancun", empleado_id=123)
    assert GUID in res["respuesta"]
    assert "pendiente" in res["respuesta"]


def test_responder_con_solicitud_aprobada():
    orquestador = Orchestrator(
        agente_solicitudes=FakeSolicitudes("aprobada"), agente_viaje=FakeViajes()
    )
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


def test_solicitud_aprobada_activa_agente_viaje():
    viajes = FakeViajes()
    orquestador = Orchestrator(
        agente_solicitudes=FakeSolicitudes("aprobada"), agente_viaje=viajes
    )
    res = orquestador.responder("Quiero vacaciones a Cancun", empleado_id=123)
    assert len(viajes.llamados) == 1
    assert viajes.llamados[0]["destino"] == "Cancun"
    assert viajes.llamados[0]["fecha_inicio"] == "2026-09-01"
    assert "Ideas de viaje para Cancun" in res["respuesta"]
    assert "aprobada" in res["respuesta"]


def test_solicitud_pendiente_no_activa_agente_viaje():
    viajes = FakeViajes()
    orquestador = Orchestrator(
        agente_solicitudes=FakeSolicitudes("pendiente"), agente_viaje=viajes
    )
    res = orquestador.responder("Quiero vacaciones a Cancun", empleado_id=123)
    assert viajes.llamados == []
    assert "Ideas de viaje" not in res["respuesta"]


def test_solicitud_aprobada_sin_destino_no_activa_agente_viaje():
    viajes = FakeViajes()
    orquestador = Orchestrator(
        agente_solicitudes=FakeSolicitudes("aprobada", destino=None),
        agente_viaje=viajes,
    )
    res = orquestador.responder("Quiero vacaciones", empleado_id=123)
    assert viajes.llamados == []
    assert "Ideas de viaje" not in res["respuesta"]


def test_error_del_agente_viaje_no_rompe_la_respuesta():
    class ViajesRotos:
        def run(self, **kwargs):
            raise RuntimeError("fallo inesperado")

    orquestador = Orchestrator(
        agente_solicitudes=FakeSolicitudes("aprobada"), agente_viaje=ViajesRotos()
    )
    res = orquestador.responder("Quiero vacaciones a Cancun", empleado_id=123)
    assert GUID in res["respuesta"]
    assert "aprobada" in res["respuesta"]
