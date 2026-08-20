"""Script de prueba manual del agente_viaje, sin pasar por FastAPI.

Ejecutar con: python probar_agente2.py
Requiere HF_TOKEN configurado en .env.
"""

from app.agents.viaje.agent import buscar_info_viaje

DESTINOS_DE_PRUEBA = [
    ("Panamá", "2026-09-10", "2026-09-15"),
    ("Cancún", "2026-10-01", "2026-10-07"),
    ("Buenos Aires", "2026-12-05", "2026-12-12"),
]

if __name__ == "__main__":
    for destino, inicio, fin in DESTINOS_DE_PRUEBA:
        print(f"\n=== {destino} ({inicio} a {fin}) ===")
        try:
            info = buscar_info_viaje(destino, inicio, fin)
            print(info)
        except Exception as exc:
            print(f"Error: {exc}")
