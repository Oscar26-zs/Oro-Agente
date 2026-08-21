from ...utils.logger import get_logger

logger = get_logger(__name__)


def buscar_clima(
    destino: str,
    fecha_inicio: str | None = None,
    fecha_fin: str | None = None,
) -> dict:
    logger.info("ViajeTools [mock] clima para %s", destino)
    return {
        "destino": destino,
        "resumen": (
            f"Clima tipico en {destino}: calido durante el dia y fresco en la noche, "
            "con baja probabilidad de lluvia."
        ),
        "temperatura_min": 22,
        "temperatura_max": 31,
    }


def buscar_vuelos(
    destino: str,
    fecha_inicio: str | None = None,
    fecha_fin: str | None = None,
) -> dict:
    logger.info("ViajeTools [mock] vuelos para %s", destino)
    return {
        "destino": destino,
        "opciones": [
            {"aerolinea": "Aerolinea Andina", "precio_usd": 320, "escalas": 0},
            {"aerolinea": "Vuelos del Sur", "precio_usd": 260, "escalas": 1},
        ],
        "resumen": f"Vuelos de ejemplo hacia {destino} entre {fecha_inicio} y {fecha_fin}.",
    }


def buscar_hoteles(
    destino: str,
    fecha_inicio: str | None = None,
    fecha_fin: str | None = None,
) -> dict:
    logger.info("ViajeTools [mock] hoteles para %s", destino)
    return {
        "destino": destino,
        "opciones": [
            {"nombre": f"Hotel Central {destino}", "precio_noche_usd": 85, "estrellas": 4},
            {"nombre": f"Hostal Buen Precio {destino}", "precio_noche_usd": 35, "estrellas": 3},
        ],
        "resumen": f"Alojamientos de ejemplo en {destino} para las fechas indicadas.",
    }


def sugerir_actividades(
    destino: str,
    fecha_inicio: str | None = None,
    fecha_fin: str | None = None,
) -> dict:
    logger.info("ViajeTools [mock] actividades para %s", destino)
    return {
        "destino": destino,
        "actividades": [
            f"Tour por el centro historico de {destino}",
            "Excursion de un dia a las afueras",
            "Ruta gastronomica local",
        ],
        "resumen": f"Actividades populares de ejemplo en {destino}.",
    }
