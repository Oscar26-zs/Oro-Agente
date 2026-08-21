from app.store.viajes_store import ViajesStore

GUID = "3f2504e0-4f89-41d3-9a0c-0305e82c3301"


def test_guardar_y_obtener_viaje(tmp_path):
    store = ViajesStore(path=tmp_path / "store.json")
    store.guardar_viaje(
        solicitud_id=GUID,
        empleado_id="123",
        destino="Cancun",
        fecha_inicio="2026-09-01",
        fecha_fin="2026-09-15",
    )
    viaje = store.obtener(GUID)
    assert viaje is not None
    assert viaje["empleado_id"] == "123"
    assert viaje["destino"] == "Cancun"
    assert viaje["fecha_inicio"] == "2026-09-01"
    assert viaje["recomendaciones_entregadas"] is False


def test_persistencia_entre_instancias(tmp_path):
    ruta = tmp_path / "store.json"
    store1 = ViajesStore(path=ruta)
    store1.guardar_viaje(GUID, empleado_id="123", destino="Cancun")

    store2 = ViajesStore(path=ruta)
    viaje = store2.obtener(GUID)
    assert viaje is not None
    assert viaje["destino"] == "Cancun"


def test_pendientes_filtran_por_empleado_y_flag(tmp_path):
    store = ViajesStore(path=tmp_path / "store.json")
    store.guardar_viaje("aaa", empleado_id="123", destino="Cancun")
    store.guardar_viaje("bbb", empleado_id="456", destino="Panama")
    store.marcar_entregado("bbb")

    pendientes = store.viajes_pendientes_de_empleado("123")
    assert len(pendientes) == 1
    assert pendientes[0]["solicitud_id"] == "aaa"

    assert store.viajes_pendientes_de_empleado("456") == []
    assert store.viajes_pendientes_de_empleado(None) == []


def test_marcar_entregado_excluye_de_pendientes(tmp_path):
    store = ViajesStore(path=tmp_path / "store.json")
    store.guardar_viaje(GUID, empleado_id="123", destino="Cancun")

    assert len(store.viajes_pendientes_de_empleado("123")) == 1
    store.marcar_entregado(GUID)
    assert store.viajes_pendientes_de_empleado("123") == []
    assert store.obtener(GUID)["recomendaciones_entregadas"] is True


def test_guardar_actualiza_sin_perder_flag(tmp_path):
    store = ViajesStore(path=tmp_path / "store.json")
    store.guardar_viaje(GUID, empleado_id="123")
    store.marcar_entregado(GUID)

    store.guardar_viaje(GUID, empleado_id="123", destino="Cancun")
    viaje = store.obtener(GUID)
    assert viaje["destino"] == "Cancun"
    assert viaje["recomendaciones_entregadas"] is True


def test_guardar_sin_solicitud_id_no_hace_nada(tmp_path):
    store = ViajesStore(path=tmp_path / "store.json")
    store.guardar_viaje("", empleado_id="123", destino="Cancun")
    assert store.viajes_pendientes_de_empleado("123") == []


def test_store_corrupto_inicia_vacio(tmp_path):
    ruta = tmp_path / "store.json"
    ruta.write_text("{no es json", encoding="utf-8")
    store = ViajesStore(path=ruta)
    assert store.viajes_pendientes_de_empleado("123") == []


def test_eliminar_quita_la_entrada(tmp_path):
    store = ViajesStore(path=tmp_path / "store.json")
    store.guardar_viaje(GUID, empleado_id="123", destino="Cancun")

    assert store.eliminar(GUID) is True
    assert store.obtener(GUID) is None
    assert store.viajes_pendientes_de_empleado("123") == []
    assert store.eliminar(GUID) is False


def test_eliminar_persiste_en_disco(tmp_path):
    ruta = tmp_path / "store.json"
    s1 = ViajesStore(path=ruta)
    s1.guardar_viaje(GUID, empleado_id="123")
    s1.eliminar(GUID)

    s2 = ViajesStore(path=ruta)
    assert s2.obtener(GUID) is None


def test_ultimo_viaje_de_empleado(tmp_path):
    store = ViajesStore(path=tmp_path / "store.json")

    assert store.ultimo_viaje_de_empleado("123") is None
    assert store.ultimo_viaje_de_empleado(None) is None

    store.guardar_viaje("aaa", empleado_id="123", destino="Cancun")
    store.guardar_viaje("bbb", empleado_id="456", destino="Panama")
    store.guardar_viaje("ccc", empleado_id="123", destino="Colombia")

    ultimo = store.ultimo_viaje_de_empleado("123")
    assert ultimo["solicitud_id"] == "ccc"  # el mas reciente gana
    assert ultimo["destino"] == "Colombia"

    # incluye tambien los ya entregados
    store.marcar_entregado("ccc")
    assert store.ultimo_viaje_de_empleado("123")["solicitud_id"] == "ccc"


def test_viajes_de_empleado_incluye_entregados(tmp_path):
    store = ViajesStore(path=tmp_path / "store.json")

    assert store.viajes_de_empleado("123") == []
    assert store.viajes_de_empleado(None) == []

    store.guardar_viaje("aaa", empleado_id="123", destino="Cancun")
    store.guardar_viaje("bbb", empleado_id="456", destino="Panama")
    store.guardar_viaje("ccc", empleado_id="123", destino="Colombia")
    store.marcar_entregado("aaa")

    viajes = store.viajes_de_empleado("123")
    ids = {v["solicitud_id"] for v in viajes}
    assert ids == {"aaa", "ccc"}  # entregados y pendientes, sin ajenos

    entregado = next(v for v in viajes if v["solicitud_id"] == "aaa")
    assert entregado["recomendaciones_entregadas"] is True
