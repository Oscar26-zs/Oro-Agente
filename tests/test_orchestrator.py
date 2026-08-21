from app.agents.solicitudes.schemas import SolicitudOutput
from app.agents.viajes.schemas import ViajeOutput
from app.orchestrator.orchestrator import Orchestrator

GUID = "3f2504e0-4f89-41d3-9a0c-0305e82c3301"
OTRO_GUID = "11111111-2222-3333-4444-555555555555"


class FakeStore:
    """Store en memoria con la misma interfaz de ViajesStore."""

    def __init__(self):
        self.viajes = {}
        self.entregados = []

    def guardar_viaje(self, solicitud_id, empleado_id=None, destino=None,
                      fecha_inicio=None, fecha_fin=None):
        if not solicitud_id:
            return
        previo = self.viajes.get(solicitud_id, {})
        self.viajes[solicitud_id] = {
            "solicitud_id": solicitud_id,
            "empleado_id": empleado_id if empleado_id is not None else previo.get("empleado_id"),
            "destino": destino or previo.get("destino"),
            "fecha_inicio": fecha_inicio or previo.get("fecha_inicio"),
            "fecha_fin": fecha_fin or previo.get("fecha_fin"),
            "recomendaciones_entregadas": previo.get("recomendaciones_entregadas", False),
        }

    def obtener(self, solicitud_id):
        return self.viajes.get(solicitud_id)

    def viajes_pendientes_de_empleado(self, empleado_id):
        if empleado_id is None:
            return []
        return [
            dict(v) for v in self.viajes.values()
            if v["empleado_id"] == str(empleado_id)
            and not v["recomendaciones_entregadas"]
        ]

    def marcar_entregado(self, solicitud_id):
        if solicitud_id in self.viajes:
            self.viajes[solicitud_id]["recomendaciones_entregadas"] = True
            self.entregados.append(solicitud_id)


class FakeEstadoClient:
    def __init__(self, estados=None, fallar=False):
        self.estados = estados or {}
        self.fallar = fallar
        self.consultas = []

    def consultar_estado(self, solicitud_id):
        self.consultas.append(solicitud_id)
        if self.fallar:
            raise RuntimeError("API de vacaciones no disponible")
        return {
            "solicitud_id": solicitud_id,
            "estado": self.estados.get(solicitud_id, "pendiente"),
        }


class FakeSolicitudes:
    def __init__(self, estado="pendiente", destino="Cancun", con_solicitud=True):
        self.estado = estado
        self.destino = destino
        self.con_solicitud = con_solicitud

    def run(self, mensaje, empleado_id=None):
        return SolicitudOutput(
            accion="crear",
            solicitud_id=GUID if self.con_solicitud else None,
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


def make_orchestrator(estado_solicitud="pendiente", destino_solicitud="Cancun",
                      store=None, estado_client=None, agente_viaje=None,
                      con_solicitud=True):
    store = store or FakeStore()
    return Orchestrator(
        agente_solicitudes=FakeSolicitudes(
            estado_solicitud, destino_solicitud, con_solicitud
        ),
        agente_viaje=agente_viaje or FakeViajes(),
        store=store,
        cliente_estado=estado_client or FakeEstadoClient(),
    ), store


# ------------------------------------------------------------------ basicos

def test_responder_devuelve_respuesta_con_estado():
    orquestador, _ = make_orchestrator("pendiente")
    res = orquestador.responder("Quiero vacaciones a Cancun", empleado_id=123)
    assert GUID in res["respuesta"]
    assert "pendiente" in res["respuesta"]


def test_responder_con_empleado_id_como_texto():
    llamado = {}

    class CapturaSolicitudes:
        def run(self, mensaje, empleado_id=None):
            llamado["empleado_id"] = empleado_id
            return SolicitudOutput(
                accion="crear",
                solicitud_id=GUID,
                estado="pendiente",
                mensaje="Solicitud creada",
            )

    orquestador = Orchestrator(
        agente_solicitudes=CapturaSolicitudes(), agente_viaje=FakeViajes(),
        store=FakeStore(), cliente_estado=FakeEstadoClient(),
    )
    orquestador.responder("Quiero vacaciones a Cancun", empleado_id=123)
    assert llamado["empleado_id"] == "123"


# ------------------------------------------------------------------ mismo turno

def test_solicitud_aprobada_activa_agente_viaje():
    store = FakeStore()
    viajes = FakeViajes()
    orquestador, _ = make_orchestrator(
        "aprobada", store=store, agente_viaje=viajes
    )
    res = orquestador.responder("Quiero vacaciones a Cancun", empleado_id=123)
    assert len(viajes.llamados) == 1
    assert viajes.llamados[0]["destino"] == "Cancun"
    assert "Ideas de viaje para Cancun" in res["respuesta"]
    assert "aprobada" in res["respuesta"]
    # el mismo turno marca la solicitud como entregada para no repetir
    assert GUID in store.entregados


def test_solicitud_pendiente_no_activa_agente_viaje():
    viajes = FakeViajes()
    orquestador, _ = make_orchestrator("pendiente", agente_viaje=viajes)
    res = orquestador.responder("Quiero vacaciones a Cancun", empleado_id=123)
    assert viajes.llamados == []
    assert "Ideas de viaje" not in res["respuesta"]


def test_solicitud_aprobada_sin_destino_no_activa_agente_viaje():
    viajes = FakeViajes()
    orquestador, _ = make_orchestrator("aprobada", destino_solicitud=None,
                                       agente_viaje=viajes)
    res = orquestador.responder("Quiero vacaciones", empleado_id=123)
    assert viajes.llamados == []
    assert "Ideas de viaje" not in res["respuesta"]


def test_error_del_agente_viaje_no_rompe_la_respuesta():
    class ViajesRotos:
        def run(self, **kwargs):
            raise RuntimeError("fallo inesperado")

    orquestador, _ = make_orchestrator("aprobada", agente_viaje=ViajesRotos())
    res = orquestador.responder("Quiero vacaciones a Cancun", empleado_id=123)
    assert GUID in res["respuesta"]
    assert "aprobada" in res["respuesta"]


# ------------------------------------------------------------------ contexto

def test_creacion_registra_contexto_en_el_store():
    store = FakeStore()
    orquestador, _ = make_orchestrator("pendiente", store=store)
    orquestador.responder("Vacaciones del 1 al 15 a Cancun", empleado_id="123")
    viaje = store.obtener(GUID)
    assert viaje is not None
    assert viaje["empleado_id"] == "123"
    assert viaje["destino"] == "Cancun"
    assert viaje["fecha_inicio"] == "2026-09-01"


def test_aprobacion_previa_entrega_recomendaciones_una_vez():
    store = FakeStore()
    store.guardar_viaje(
        OTRO_GUID, empleado_id="123", destino="Cancun",
        fecha_inicio="2026-09-01", fecha_fin="2026-09-15",
    )
    estado_client = FakeEstadoClient(estados={OTRO_GUID: "aprobada"})
    viajes = FakeViajes()
    orquestador, _ = make_orchestrator(
        "pendiente", store=store, estado_client=estado_client,
        agente_viaje=viajes, con_solicitud=False,
    )

    primera = orquestador.responder("hola", empleado_id="123")
    assert estado_client.consultas == [OTRO_GUID]
    assert len(viajes.llamados) == 1
    assert viajes.llamados[0]["destino"] == "Cancun"
    assert "APROBADA" in primera["respuesta"]
    assert "Ideas de viaje para Cancun" in primera["respuesta"]
    assert OTRO_GUID in store.entregados

    segunda = orquestador.responder("otra consulta", empleado_id="123")
    assert len(viajes.llamados) == 1
    assert "Ideas de viaje" not in segunda["respuesta"]


def test_solicitud_pendiente_en_store_no_entrega_nada():
    store = FakeStore()
    store.guardar_viaje(OTRO_GUID, empleado_id="123", destino="Cancun")
    estado_client = FakeEstadoClient(estados={OTRO_GUID: "pendiente"})
    viajes = FakeViajes()
    orquestador, _ = make_orchestrator(
        "pendiente", store=store, estado_client=estado_client, agente_viaje=viajes
    )

    res = orquestador.responder("hola", empleado_id="123")
    assert viajes.llamados == []
    assert "Ideas de viaje" not in res["respuesta"]
    assert store.entregados == []


def test_api_de_estado_falla_y_no_rompe_la_respuesta():
    store = FakeStore()
    store.guardar_viaje(OTRO_GUID, empleado_id="123", destino="Cancun")
    estado_client = FakeEstadoClient(fallar=True)
    viajes = FakeViajes()
    orquestador, _ = make_orchestrator(
        "pendiente", store=store, estado_client=estado_client, agente_viaje=viajes
    )

    res = orquestador.responder("hola", empleado_id="123")
    assert viajes.llamados == []
    assert store.entregados == []
    assert res["respuesta"]  # respuesta normal del agente 1


def test_aprobacion_previa_sin_destino_pide_destino():
    store = FakeStore()
    store.guardar_viaje(OTRO_GUID, empleado_id="123")  # sin destino
    estado_client = FakeEstadoClient(estados={OTRO_GUID: "aprobada"})
    viajes = FakeViajes()
    orquestador, _ = make_orchestrator(
        "pendiente", store=store, estado_client=estado_client, agente_viaje=viajes
    )

    res = orquestador.responder("hola", empleado_id="123")
    assert viajes.llamados == []  # no hay destino para investigar
    assert "APROBADA" in res["respuesta"]
    assert "Para donde quieres viajar" in res["respuesta"]
    assert OTRO_GUID in store.entregados


def test_otro_empleado_no_recibe_recomendaciones_ajenas():
    store = FakeStore()
    store.guardar_viaje(OTRO_GUID, empleado_id="999", destino="Cancun")
    estado_client = FakeEstadoClient(estados={OTRO_GUID: "aprobada"})
    viajes = FakeViajes()
    orquestador, _ = make_orchestrator(
        "pendiente", store=store, estado_client=estado_client,
        agente_viaje=viajes, con_solicitud=False,
    )

    res = orquestador.responder("hola", empleado_id="123")
    assert estado_client.consultas == []  # ni siquiera consulta por otro dueño
    assert viajes.llamados == []
    assert "Ideas de viaje" not in res["respuesta"]
