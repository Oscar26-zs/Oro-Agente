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

    def ultimo_viaje_de_empleado(self, empleado_id):
        if empleado_id is None:
            return None
        emp = str(empleado_id)
        for viaje in reversed(list(self.viajes.values())):
            if viaje["empleado_id"] == emp:
                return dict(viaje)
        return None

    def viajes_de_empleado(self, empleado_id):
        if empleado_id is None:
            return []
        emp = str(empleado_id)
        return [
            dict(v) for v in self.viajes.values()
            if v["empleado_id"] == emp
        ]

    def marcar_entregado(self, solicitud_id):
        if solicitud_id in self.viajes:
            self.viajes[solicitud_id]["recomendaciones_entregadas"] = True
            self.entregados.append(solicitud_id)

    def eliminar(self, solicitud_id):
        return self.viajes.pop(solicitud_id, None) is not None


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

def test_solicitud_aprobada_ofrece_plan_sin_entregar():
    store = FakeStore()
    viajes = FakeViajes()
    orquestador, _ = make_orchestrator(
        "aprobada", store=store, agente_viaje=viajes
    )
    res = orquestador.responder("Quiero vacaciones a Cancun", empleado_id=123)
    assert "aprobada" in res["respuesta"]
    assert "plan de viaje" in res["respuesta"]
    assert viajes.llamados == []  # no entrega nada hasta que lo pidan
    assert store.entregados == []


def test_solicitud_pendiente_no_activa_agente_viaje():
    viajes = FakeViajes()
    orquestador, _ = make_orchestrator("pendiente", agente_viaje=viajes)
    res = orquestador.responder("Quiero vacaciones a Cancun", empleado_id=123)
    assert viajes.llamados == []
    assert "Ideas de viaje" not in res["respuesta"]
    assert "plan de viaje" not in res["respuesta"]


def test_solicitud_aprobada_sin_destino_ofrece_plan():
    viajes = FakeViajes()
    orquestador, _ = make_orchestrator("aprobada", destino_solicitud=None,
                                       agente_viaje=viajes)
    res = orquestador.responder("Quiero vacaciones", empleado_id=123)
    assert viajes.llamados == []
    assert "Ideas de viaje" not in res["respuesta"]
    assert "plan de viaje" in res["respuesta"]


def test_fallo_del_agente_viaje_al_pedir_plan_no_rompe_la_respuesta():
    class ViajesRotos:
        def run(self, **kwargs):
            raise RuntimeError("fallo inesperado")

    store = FakeStore()
    store.guardar_viaje(OTRO_GUID, empleado_id="123", destino="Cancun")
    estado_client = FakeEstadoClient(estados={OTRO_GUID: "aprobada"})
    orquestador, _ = make_orchestrator(
        "pendiente", store=store, estado_client=estado_client,
        agente_viaje=ViajesRotos(), con_solicitud=False,
    )
    res = orquestador.responder("quiero mi plan de viaje", empleado_id="123")
    assert res["respuesta"]  # respuesta normal del agente 1
    assert store.entregados == []  # no se marca entregado si fallo


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


def test_peticion_plan_entrega_recomendaciones_una_vez():
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

    primera = orquestador.responder("quiero mi plan de viaje", empleado_id="123")
    assert estado_client.consultas == [OTRO_GUID]
    assert len(viajes.llamados) == 1
    assert viajes.llamados[0]["destino"] == "Cancun"
    assert "APROBADA" in primera["respuesta"]
    assert "Ideas de viaje para Cancun" in primera["respuesta"]
    assert OTRO_GUID in store.entregados

    segunda = orquestador.responder("otra vez quiero el plan", empleado_id="123")
    assert len(viajes.llamados) == 1  # no se vuelve a generar
    assert "Ya te entregue tu plan" in segunda["respuesta"]


# ------------------------------------------------------------------ accion plan

class SolicitudesPlan:
    """El clasificador detecta el pedido de plan sin palabras clave exactas."""

    def run(self, mensaje, empleado_id=None):
        return SolicitudOutput(accion="plan", estado="informativo", mensaje="")


def test_pedido_plan_por_clasificador_entrega_y_no_muestra_menu():
    store = FakeStore()
    store.guardar_viaje(
        OTRO_GUID, empleado_id="123", destino="Cancun",
        fecha_inicio="2026-09-01", fecha_fin="2026-09-15",
    )
    estado_client = FakeEstadoClient(estados={OTRO_GUID: "aprobada"})
    viajes = FakeViajes()
    orquestador, _ = make_orchestrator(
        "pendiente", store=store, estado_client=estado_client, agente_viaje=viajes,
        con_solicitud=False,
    )
    orquestador.solicitudes = SolicitudesPlan()

    res = orquestador.responder("preparame eso que me ofreciste", empleado_id="123")
    assert "Puedo ayudarte" not in res["respuesta"]  # nunca el menu fantasma
    assert "APROBADA" in res["respuesta"]
    assert "Ideas de viaje para Cancun" in res["respuesta"]
    assert OTRO_GUID in store.entregados


def test_repedido_tras_entrega_avisa_sin_regenerar():
    store = FakeStore()
    store.guardar_viaje(
        OTRO_GUID, empleado_id="123", destino="Cancun",
        fecha_inicio="2026-09-01", fecha_fin="2026-09-15",
    )
    estado_client = FakeEstadoClient(estados={OTRO_GUID: "aprobada"})
    viajes = FakeViajes()
    orquestador, _ = make_orchestrator(
        "pendiente", store=store, estado_client=estado_client, agente_viaje=viajes,
        con_solicitud=False,
    )
    orquestador.solicitudes = SolicitudesPlan()

    primera = orquestador.responder("dame mi plan", empleado_id="123")
    assert "Ideas de viaje" in primera["respuesta"]

    segunda = orquestador.responder("dame mi plan otra vez", empleado_id="123")
    assert len(viajes.llamados) == 1  # una sola generacion
    assert "Ya te entregue tu plan" in segunda["respuesta"]


def test_pedido_plan_sin_ningun_registro():
    store = FakeStore()
    orquestador, _ = make_orchestrator(
        "pendiente", store=store,
        estado_client=FakeEstadoClient(), agente_viaje=FakeViajes(),
        con_solicitud=False,
    )
    orquestador.solicitudes = SolicitudesPlan()

    res = orquestador.responder("quiero mi plan de viaje", empleado_id="123")
    assert "No tengo registro de una solicitud tuya" in res["respuesta"]
    assert "Puedo ayudarte" not in res["respuesta"]


def test_solicitud_pendiente_en_store_avisa_si_piden_plan():
    store = FakeStore()
    store.guardar_viaje(OTRO_GUID, empleado_id="123", destino="Cancun")
    estado_client = FakeEstadoClient(estados={OTRO_GUID: "pendiente"})
    viajes = FakeViajes()
    orquestador, _ = make_orchestrator(
        "pendiente", store=store, estado_client=estado_client, agente_viaje=viajes,
        con_solicitud=False,
    )

    res = orquestador.responder("quiero mi plan de viaje", empleado_id="123")
    assert viajes.llamados == []
    assert "Ideas de viaje" not in res["respuesta"]
    assert "pendiente de aprobacion" in res["respuesta"]
    assert store.entregados == []


def test_saludo_o_estado_no_consultan_ni_entregan_plan():
    store = FakeStore()
    store.guardar_viaje(OTRO_GUID, empleado_id="123", destino="Cancun")
    estado_client = FakeEstadoClient(estados={OTRO_GUID: "aprobada"})
    viajes = FakeViajes()
    orquestador, _ = make_orchestrator(
        "pendiente", store=store, estado_client=estado_client, agente_viaje=viajes,
        con_solicitud=False,
    )

    saludo = orquestador.responder("hola", empleado_id="123")
    estado_q = orquestador.responder("como va mi solicitud?", empleado_id="123")
    for res in (saludo, estado_q):
        assert "Ideas de viaje" not in res["respuesta"]
        assert "APROBADA" not in res["respuesta"]
    assert estado_client.consultas == []  # ni siquiera consulta el estado
    assert viajes.llamados == []
    assert store.entregados == []


def test_api_de_estado_falla_y_no_rompe_la_respuesta():
    store = FakeStore()
    store.guardar_viaje(OTRO_GUID, empleado_id="123", destino="Cancun")
    estado_client = FakeEstadoClient(fallar=True)
    viajes = FakeViajes()
    orquestador, _ = make_orchestrator(
        "pendiente", store=store, estado_client=estado_client, agente_viaje=viajes,
        con_solicitud=False,
    )

    res = orquestador.responder("quiero mi plan de viaje", empleado_id="123")
    assert viajes.llamados == []
    assert store.entregados == []
    assert res["respuesta"]  # respuesta normal del agente 1


def test_aprobacion_previa_sin_destino_pide_destino():
    store = FakeStore()
    store.guardar_viaje(OTRO_GUID, empleado_id="123")  # sin destino
    estado_client = FakeEstadoClient(estados={OTRO_GUID: "aprobada"})
    viajes = FakeViajes()
    orquestador, _ = make_orchestrator(
        "pendiente", store=store, estado_client=estado_client, agente_viaje=viajes,
        con_solicitud=False,
    )

    res = orquestador.responder("quiero mi plan de viaje", empleado_id="123")
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


def test_solicitud_404_se_retira_del_contexto_y_no_reintenta():
    store = FakeStore()
    store.guardar_viaje(OTRO_GUID, empleado_id="123", destino="Cancun")

    class EstadoClient404:
        def __init__(self):
            self.consultas = []

        def consultar_estado(self, solicitud_id):
            self.consultas.append(solicitud_id)
            raise RuntimeError(
                "El sistema de vacaciones respondio 404: Solicitud no encontrada."
            )

    estado_client = EstadoClient404()
    orquestador, _ = make_orchestrator(
        "pendiente", store=store, estado_client=estado_client,
        agente_viaje=FakeViajes(), con_solicitud=False,
    )

    primera = orquestador.responder("quiero mi plan de viaje", empleado_id="123")
    assert OTRO_GUID not in store.viajes  # retirado del contexto

    segunda = orquestador.responder("quiero el plan otra vez", empleado_id="123")
    assert len(estado_client.consultas) == 1  # no vuelve a consultar
    assert segunda["respuesta"]


def test_respuesta_de_error_muestra_solo_el_mensaje():
    class SolicitudesError:
        def run(self, mensaje, empleado_id=None):
            return SolicitudOutput(
                accion="consultar",
                solicitud_id=GUID,
                estado="error",
                mensaje="La solicitud no existe en el sistema de vacaciones.",
            )

    orquestador, _ = make_orchestrator()
    orquestador.solicitudes = SolicitudesError()
    res = orquestador.responder("como va mi solicitud", empleado_id="123")
    assert "con estado error" not in res["respuesta"]
    assert "no existe" in res["respuesta"]


# ------------------------------------------------------------------ ayuda

class SolicitudesAyuda:
    def run(self, mensaje, empleado_id=None):
        return SolicitudOutput(
            accion="ayuda",
            estado="informativo",
            mensaje=(
                "Hola! Puedo ayudarte a:\n"
                "- Solicitar vacaciones: dime las fechas y el destino.\n"
                "- Consultar una solicitud: pasame su identificador."
            ),
        )


def test_saludo_recibe_menu_y_no_pide_fechas():
    orquestador, _ = make_orchestrator("pendiente")
    orquestador.solicitudes = SolicitudesAyuda()
    res = orquestador.responder("hola", empleado_id="123")
    assert "Puedo ayudarte" in res["respuesta"]
    assert "necesito que me indiques el destino" not in res["respuesta"]


def test_consulta_aprobada_ofrece_plan_sin_entregarlo():
    class SolicitudesConsultaAprobada:
        def run(self, mensaje, empleado_id=None):
            return SolicitudOutput(
                accion="consultar",
                solicitud_id=OTRO_GUID,
                estado="aprobada",
                mensaje=f"La solicitud {OTRO_GUID} figura con estado aprobada.",
            )

    store = FakeStore()
    store.guardar_viaje(
        OTRO_GUID, empleado_id="123", destino="Cancun",
        fecha_inicio="2026-09-01", fecha_fin="2026-09-15",
    )
    viajes = FakeViajes()
    orquestador, _ = make_orchestrator(
        "pendiente", store=store,
        estado_client=FakeEstadoClient(estados={OTRO_GUID: "aprobada"}),
        agente_viaje=viajes,
    )
    orquestador.solicitudes = SolicitudesConsultaAprobada()

    res = orquestador.responder("como va mi solicitud?", empleado_id="123")
    assert "aprobada" in res["respuesta"]
    assert "plan de viaje" in res["respuesta"]  # ofrece...
    assert "Ideas de viaje" not in res["respuesta"]  # ...pero no entrega
    assert viajes.llamados == []

    res2 = orquestador.responder("quiero mi plan de viaje", empleado_id="123")
    assert "Ideas de viaje para Cancun" in res2["respuesta"]  # ahora si
    assert OTRO_GUID in store.entregados
