"""Pruebas del flujo de orquestación entre ambos agentes."""

from unittest.mock import Mock, patch

from app.orchestrator import orchestrator


def test_debe_investigar_viaje_solo_si_aprobada():
    assert orchestrator.debe_investigar_viaje("aprobada") is True
    assert orchestrator.debe_investigar_viaje("pendiente") is False
    assert orchestrator.debe_investigar_viaje("rechazada") is False
    assert orchestrator.debe_investigar_viaje("cualquier_otra_cosa") is False


def test_procesar_mensaje_llama_al_orquestador_con_la_tarea_correcta():
    empleado_id = "2c2a9142-4f21-4e46-8b70-a998f6e3cd32"
    agente_falso = Mock()
    agente_falso.run.return_value = "Tu solicitud fue creada y está pendiente."

    with patch.object(orchestrator, "crear_orquestador", return_value=agente_falso) as mock_crear:
        respuesta = orchestrator.procesar_mensaje("Quiero vacaciones", empleado_id=empleado_id)

    mock_crear.assert_called_once_with(empleado_id)
    assert respuesta == "Tu solicitud fue creada y está pendiente."
    tarea_usada = agente_falso.run.call_args[0][0]
    assert empleado_id in tarea_usada
    assert "Quiero vacaciones" in tarea_usada
