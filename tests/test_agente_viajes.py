import pytest

from app.agents.viajes.agent import AgenteViaje
from app.agents.viajes.schemas import ViajeOutput
from app.agents.viajes.tools import (
    buscar_clima,
    buscar_hoteles,
    buscar_vuelos,
    sugerir_actividades,
)


class FakeResponse:
    def __init__(self, contenido):
        self.content = contenido


class FakeModel:
    def __init__(self, texto="Te recomiendo el Hotel Central Cancun."):
        self.texto = texto
        self.llamadas = []

    def generate(self, messages, **kwargs):
        self.llamadas.append(messages)
        return FakeResponse(self.texto)


class FakeModelRoto:
    def generate(self, messages, **kwargs):
        raise RuntimeError("OpenRouter no disponible")


def test_tools_mock_devuelven_datos():
    clima = buscar_clima("Cancun", "2026-09-01", "2026-09-15")
    vuelos = buscar_vuelos("Cancun", "2026-09-01", "2026-09-15")
    hoteles = buscar_hoteles("Cancun", "2026-09-01", "2026-09-15")
    actividades = sugerir_actividades("Cancun", "2026-09-01", "2026-09-15")

    assert "Cancun" in clima["resumen"]
    assert len(vuelos["opciones"]) >= 1
    assert len(hoteles["opciones"]) >= 1
    assert len(actividades["actividades"]) >= 1


def test_agente_viaje_redacta_con_modelo():
    modelo = FakeModel("Disfruta Cancun: hotel X y vuelo Y.")
    agente = AgenteViaje(model=modelo)
    out = agente.run(
        destino="Cancun",
        fecha_inicio="2026-09-01",
        fecha_fin="2026-09-15",
        mensaje="Quiero vacaciones a Cancun",
    )
    assert isinstance(out, ViajeOutput)
    assert out.recomendaciones == "Disfruta Cancun: hotel X y vuelo Y."
    assert out.destino == "Cancun"
    assert len(modelo.llamadas) == 1
    user_content = modelo.llamadas[0][-1]["content"]
    assert "Cancun" in user_content
    assert "2026-09-01" in user_content


def test_agente_viaje_fallback_sin_modelo():
    agente = AgenteViaje(model=FakeModelRoto())
    out = agente.run(destino="Cancun", fecha_inicio="2026-09-01")
    assert isinstance(out, ViajeOutput)
    assert "Clima:" in out.recomendaciones
    assert "Vuelo sugerido:" in out.recomendaciones
    assert "Alojamiento economico:" in out.recomendaciones
    assert "Actividades:" in out.recomendaciones


def test_agente_viaje_fallback_con_texto_vacio_del_modelo():
    agente = AgenteViaje(model=FakeModel(texto=""))
    out = agente.run(destino="Cancun")
    assert "Clima:" in out.recomendaciones


@pytest.mark.parametrize(
    "destino",
    ["Cancun", "Cartagena de Indias"],
)
def test_tools_aceptan_cualquier_destino(destino):
    datos = buscar_clima(destino)
    assert destino in datos["resumen"]
