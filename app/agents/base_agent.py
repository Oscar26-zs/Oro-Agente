"""Interfaz/contrato común que deben cumplir todos los agentes, para poder
cambiar de framework de IA sin afectar al resto del proyecto."""

from typing import Protocol, runtime_checkable


@runtime_checkable
class AgenteEjecutable(Protocol):
    """Cualquier agente (de smolagents u otro framework) usado en este
    proyecto debe cumplir esta interfaz mínima: tener nombre/descripción y
    poder ejecutar una tarea en texto."""

    name: str
    description: str

    def run(self, task: str) -> object: ...
