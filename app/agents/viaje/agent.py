"""Define el agente_viaje: investiga información del destino usando
las tools de este mismo paquete."""

from smolagents import CodeAgent, WebSearchTool

from app.agents.viaje.tools import ClimaTool, parsear_json_respuesta
from app.config import MAX_STEPS_VIAJE, get_model

INSTRUCCIONES = """\
Eres un agente investigador de viajes. Dado un destino y un rango de fechas,
investiga usando SOLO tus tools (búsqueda web y consulta de clima):

- vuelos: opciones de vuelo o aerolíneas que suelen operar hacia el destino
- hoteles: 2-4 opciones de hospedaje con su zona o nombre
- clima: usa SIEMPRE la tool consultar_clima para el dato de clima, nunca lo inventes
- actividades: 3-5 actividades o lugares turísticos recomendados

No inventes datos que no encontraste en tus búsquedas. Si no encuentras algo,
indícalo como una lista vacía o un texto breve que diga que no se encontró
información, en vez de inventar.

Tu respuesta final DEBE ser exclusivamente un JSON con esta forma exacta, sin
texto adicional antes ni después:

{"vuelos": [...], "hoteles": [...], "clima": "...", "actividades": [...]}
"""


def crear_agente_viaje() -> CodeAgent:
    return CodeAgent(
        tools=[WebSearchTool(), ClimaTool()],
        model=get_model(),
        name="agente_viaje",
        description=(
            "Investiga vuelos, hoteles, clima y actividades de un destino turístico. "
            "Llámalo con el destino y las fechas del viaje como tarea."
        ),
        instructions=INSTRUCCIONES,
        max_steps=MAX_STEPS_VIAJE,
        additional_authorized_imports=["json"],
    )


def buscar_info_viaje(destino: str, fecha_inicio: str, fecha_fin: str) -> dict:
    """Función reutilizable: ejecuta el agente_viaje de forma aislada y
    devuelve la información del destino ya parseada como dict."""
    agente = crear_agente_viaje()
    tarea = (
        f"Investiga información de viaje para el destino '{destino}', "
        f"para un viaje del {fecha_inicio} al {fecha_fin}."
    )
    resultado = agente.run(tarea)
    return parsear_json_respuesta(str(resultado))
