"""Script de prueba manual del Agente 1 (gestor de solicitudes) contra el
sistema C# MVC real en VACACIONES_API_URL (por defecto http://localhost:5051).

Ejecutar con: python probar_agente1.py

A diferencia de probar_agente2.py, este script NO requiere HF_TOKEN: llama
directamente a las tools (crear_solicitud_vacaciones, consultar_estado_solicitud),
que a su vez hacen las llamadas HTTP reales al sistema C# MVC. Si ese sistema
no está corriendo, no tiene la API key configurada, o responde con error, el
script lo indica de forma clara en vez de mostrar un traceback crudo.

Requiere VACACIONES_API_KEY configurado en .env con el mismo valor que
AgenteIA:ApiKey del lado C#.
"""

import json
import sys

from app.agents.solicitudes.tools import consultar_estado_solicitud, crear_solicitud_vacaciones

# Id (Guid) de un empleado real ya sembrado por SeedData.cs del lado C#
# (por defecto corresponde a empleado@example.com). Si tu base de datos local
# es distinta, reemplázalo por el Id real, por ejemplo consultando:
#   sqlcmd -S "(localdb)\MSSQLLocalDB" -d VacacionesDb_Dev -C ^
#     -Q "SELECT Id, Email FROM Empleado WHERE Email = 'empleado@example.com';"
EMPLEADO_ID_DE_PRUEBA = "2c2a9142-4f21-4e46-8b70-a998f6e3cd32"
DESTINO_DE_PRUEBA = "Panamá"
FECHA_INICIO_DE_PRUEBA = "2026-09-10"
FECHA_FIN_DE_PRUEBA = "2026-09-15"


def main() -> int:
    print("=== Prueba de Agente 1: crear solicitud de vacaciones ===")
    salida_crear = crear_solicitud_vacaciones(
        empleado_id=EMPLEADO_ID_DE_PRUEBA,
        destino=DESTINO_DE_PRUEBA,
        fecha_inicio=FECHA_INICIO_DE_PRUEBA,
        fecha_fin=FECHA_FIN_DE_PRUEBA,
    )
    resultado_crear = json.loads(salida_crear)
    print(salida_crear)

    if "error" in resultado_crear:
        print(
            "\nNo se pudo crear la solicitud. Verifica que el sistema C# MVC esté "
            "corriendo en la URL configurada en VACACIONES_API_URL, que exponga "
            "POST /api/vacaciones/solicitar, y que VACACIONES_API_KEY coincida con "
            "AgenteIA:ApiKey del lado C#.\n"
            f"Detalle: {resultado_crear['error']}"
        )
        return 1

    solicitud_id = resultado_crear["solicitudId"]

    print(f"\n=== Prueba de Agente 1: consultar estado de la solicitud {solicitud_id} ===")
    salida_estado = consultar_estado_solicitud(solicitud_id=solicitud_id)
    resultado_estado = json.loads(salida_estado)
    print(salida_estado)

    if "error" in resultado_estado:
        print(
            "\nNo se pudo consultar el estado de la solicitud. Verifica que el "
            "sistema C# MVC exponga GET /api/vacaciones/{id}/estado.\n"
            f"Detalle: {resultado_estado['error']}"
        )
        return 1

    estado = resultado_estado["estado"]
    if estado == "pendiente":
        print("\nLa solicitud está pendiente de aprobación. No hay nada más que hacer por ahora.")
    elif estado == "aprobada":
        print("\nLa solicitud fue aprobada. Está lista para pasar al agente_viaje.")
    elif estado == "rechazada":
        print("\nLa solicitud fue rechazada.")
    else:
        print(f"\nEstado no reconocido: {estado!r}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
