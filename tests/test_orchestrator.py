"""Pruebas del flujo de orquestación entre ambos agentes."""

import json
from unittest.mock import Mock, patch

from app.orchestrator import orchestrator


def test_debe_investigar_viaje_solo_si_aprobada():
    assert orchestrator.debe_investigar_viaje("aprobada") is True
    assert orchestrator.debe_investigar_viaje("pendiente") is False
    assert orchestrator.debe_investigar_viaje("rechazada") is False
    assert orchestrator.debe_investigar_viaje("cualquier_otra_cosa") is False


def _agente_solicitudes_falso(respuesta_json: str) -> Mock:
    agente = Mock()
    agente.run.return_value = respuesta_json
    return agente


def test_procesar_mensaje_pendiente_no_llama_al_agente_viaje():
    empleado_id = "2c2a9142-4f21-4e46-8b70-a998f6e3cd32"
    respuesta = json.dumps(
        {"solicitudId": "1", "estado": "pendiente", "mensaje": "Tu solicitud está pendiente."},
        ensure_ascii=False,
    )
    agente = _agente_solicitudes_falso(respuesta)

    with patch.object(orchestrator, "crear_agente_solicitudes", return_value=agente), \
         patch.object(orchestrator, "buscar_info_viaje") as viaje_falso:
        respuesta_final = orchestrator.procesar_mensaje("Quiero vacaciones", empleado_id)

    assert respuesta_final == "Tu solicitud está pendiente."
    viaje_falso.assert_not_called()
    tarea_usada = agente.run.call_args[0][0]
    assert empleado_id in tarea_usada
    assert "Quiero vacaciones" in tarea_usada


def test_procesar_mensaje_aprobada_investiga_y_compone_respuesta():
    respuesta = json.dumps(
        {
            "estado": "aprobada",
            "destino": "Panamá",
            "fecha_inicio": "2026-10-10",
            "fecha_fin": "2026-10-12",
            "mensaje": "Aprobada.",
        },
        ensure_ascii=False,
    )

    with patch.object(
        orchestrator, "crear_agente_solicitudes", return_value=_agente_solicitudes_falso(respuesta)
    ), patch.object(orchestrator, "buscar_info_viaje") as viaje_falso:
        viaje_falso.return_value = {
            "vuelos": ["Copa Airlines"],
            "hoteles": [],
            "clima": "Panamá: soleado",
            "actividades": ["Casco Antiguo"],
        }
        respuesta_final = orchestrator.procesar_mensaje("Vacaciones en Panamá", empleado_id="e1")

    viaje_falso.assert_called_once_with("Panamá", "2026-10-10", "2026-10-12")
    assert "aprobada" in respuesta_final.lower()
    assert "Copa Airlines" in respuesta_final
    assert "Casco Antiguo" in respuesta_final
    assert "No se encontró información" in respuesta_final  # hoteles vacíos


def test_procesar_mensaje_con_error_devuelve_el_mensaje_del_json():
    respuesta = json.dumps(
        {"error": "conexion", "mensaje": "No pude comunicarme con el sistema de vacaciones."},
        ensure_ascii=False,
    )

    with patch.object(
        orchestrator, "crear_agente_solicitudes", return_value=_agente_solicitudes_falso(respuesta)
    ), patch.object(orchestrator, "buscar_info_viaje") as viaje_falso:
        respuesta_final = orchestrator.procesar_mensaje("Hola", empleado_id="e1")

    assert respuesta_final == "No pude comunicarme con el sistema de vacaciones."
    viaje_falso.assert_not_called()


def test_procesar_mensaje_con_salida_no_json_devuelve_error_interno():
    with patch.object(
        orchestrator,
        "crear_agente_solicitudes",
        return_value=_agente_solicitudes_falso("esto no es json"),
    ):
        respuesta_final = orchestrator.procesar_mensaje("Hola", empleado_id="e1")

    assert respuesta_final == orchestrator.MENSAJE_ERROR_INTERNO
