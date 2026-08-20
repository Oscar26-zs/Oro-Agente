"""Configuración de logging compartida por agentes, orquestador y API,
para registrar eventos y errores de forma consistente."""

import logging
import os

_configurado = False


def get_logger(name: str) -> logging.Logger:
    global _configurado
    if not _configurado:
        logging.basicConfig(
            level=os.getenv("LOG_LEVEL", "INFO"),
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        )
        _configurado = True
    return logging.getLogger(name)
