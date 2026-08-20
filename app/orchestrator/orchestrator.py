"""Coordina agente_solicitudes y agente_viaje. Aplica la regla de negocio:
solo invoca al agente de viaje si el estado de la solicitud es "aprobada"."""

from smolagents import CodeAgent

from app.agents.solicitudes.agent import crear_agente_solicitudes
from app.agents.viaje.agent import crear_agente_viaje
from app.config import get_model

INSTRUCCIONES = """\
Eres el orquestador de un asistente de vacaciones para empleados. Para cada
mensaje del empleado debes:

1. Llamar SIEMPRE primero a agente_solicitudes con el mensaje del empleado,
   para crear o consultar su solicitud de vacaciones.
2. Leer el campo "estado" del JSON que devuelve agente_solicitudes.
3. Si el estado es "pendiente" o "rechazada", o si hubo un error, responde al
   empleado informando eso de forma clara y breve. NO llames a agente_viaje.
4. Solo si el estado es EXACTAMENTE "aprobada", llama también a agente_viaje
   con el destino y las fechas de la solicitud, e incluye esa información
   (vuelos, hoteles, clima, actividades) en tu respuesta final.
5. Responde siempre en español, en un mensaje breve y natural dirigido al
   empleado, nunca como JSON crudo.
"""


def debe_investigar_viaje(estado: str) -> bool:
    """Regla de negocio: solo se investiga el viaje si la solicitud fue aprobada."""
    return estado == "aprobada"


def crear_orquestador(empleado_id: str) -> CodeAgent:
    agente_solicitudes = crear_agente_solicitudes(empleado_id)
    agente_viaje = crear_agente_viaje()

    return CodeAgent(
        tools=[],
        model=get_model(),
        managed_agents=[agente_solicitudes, agente_viaje],
        instructions=INSTRUCCIONES,
        max_steps=10,
    )


def procesar_mensaje(mensaje: str, empleado_id: str) -> str:
    orquestador = crear_orquestador(empleado_id)
    tarea = f'Mensaje del empleado (empleadoId={empleado_id}): "{mensaje}"'
    resultado = orquestador.run(tarea)
    return str(resultado)
