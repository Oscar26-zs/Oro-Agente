"""Funciones que el agente usa como herramientas: buscar clima,
vuelos, hoteles y actividades del destino."""

import json
import re

import requests
from smolagents import Tool


class ClimaTool(Tool):
    name = "consultar_clima"
    description = (
        "Consulta el clima actual de una ciudad o destino usando wttr.in. "
        "Devuelve una descripción corta en texto plano."
    )
    inputs = {
        "destino": {"type": "string", "description": "Ciudad o destino, ej. 'Panamá'."},
    }
    output_type = "string"

    def forward(self, destino: str) -> str:
        try:
            response = requests.get(f"https://wttr.in/{destino}", params={"format": "3"}, timeout=10)
            response.raise_for_status()
            return response.text.strip()
        except requests.exceptions.RequestException:
            return f"No se pudo obtener el clima de {destino} en este momento."


def parsear_json_respuesta(texto: str) -> dict:
    """Extrae el primer objeto JSON válido de un texto, aunque el modelo
    haya agregado explicaciones u otro texto alrededor."""
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        pass

    coincidencia = re.search(r"\{.*\}", texto, re.DOTALL)
    if coincidencia:
        try:
            return json.loads(coincidencia.group(0))
        except json.JSONDecodeError:
            pass

    raise ValueError(f"No se pudo extraer un JSON válido de la respuesta del agente: {texto!r}")
