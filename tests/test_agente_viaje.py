"""Pruebas del agente de viaje y sus tools de búsqueda."""

from unittest.mock import Mock, patch

import pytest
import requests

from app.agents.viaje.tools import ClimaTool, parsear_json_respuesta


def test_parsear_json_respuesta_json_limpio():
    texto = '{"vuelos": [], "hoteles": [], "clima": "soleado", "actividades": []}'
    resultado = parsear_json_respuesta(texto)
    assert resultado["clima"] == "soleado"


def test_parsear_json_respuesta_con_texto_extra_alrededor():
    texto = (
        "Aquí tienes la información solicitada:\n"
        '{"vuelos": ["Copa Airlines"], "hoteles": ["Hotel Central"], '
        '"clima": "cálido", "actividades": ["Casco Viejo"]}\n'
        "Espero que te sea útil."
    )
    resultado = parsear_json_respuesta(texto)
    assert resultado["vuelos"] == ["Copa Airlines"]
    assert resultado["actividades"] == ["Casco Viejo"]


def test_parsear_json_respuesta_sin_json_lanza_error():
    with pytest.raises(ValueError):
        parsear_json_respuesta("esto no tiene ningún JSON adentro")


def test_parsear_json_respuesta_acepta_repr_de_dict_python():
    texto = (
        "{'solicitudId': 'a1b2c3d4', 'estado': 'pendiente', 'destino': 'Panamá', "
        "'mensaje': 'La solicitud fue registrada.'}"
    )
    resultado = parsear_json_respuesta(texto)
    assert resultado["estado"] == "pendiente"
    assert resultado["destino"] == "Panamá"


def test_clima_tool_devuelve_texto_de_wttr():
    tool = ClimaTool()
    respuesta_falsa = Mock()
    respuesta_falsa.raise_for_status = lambda: None
    respuesta_falsa.text = "Panamá: soleado +30C"

    with patch("requests.get", return_value=respuesta_falsa):
        resultado = tool.forward("Panamá")

    assert "Panamá" in resultado


def test_clima_tool_maneja_error_de_red():
    with patch("requests.get", side_effect=requests.exceptions.RequestException()):
        tool = ClimaTool()
        resultado = tool.forward("Ciudad Inexistente")

    assert "No se pudo obtener el clima" in resultado
