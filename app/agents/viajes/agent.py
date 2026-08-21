import json

from ..base_agent import BaseAgent
from ..llm import build_model
from ...utils.logger import get_logger
from .schemas import ViajeInput, ViajeOutput
from .tools import (
    buscar_clima,
    buscar_hoteles,
    buscar_vuelos,
    sugerir_actividades,
)

logger = get_logger(__name__)

RECOMENDACION_SYSTEM = (
    "Eres un asesor de viajes. Al empleado ya le APROBARON sus vacaciones y le "
    "entregamos el destino, las fechas y datos de referencia (clima, vuelos, "
    "hoteles y actividades).\n"
    "Redacta una recomendacion breve (maximo 8 lineas), amable y util, en espanol. "
    "Menciona lo mas relevante de cada dato entregado. No inventes datos que no "
    "aparezcan en la informacion recibida."
)


class AgenteViaje(BaseAgent):
    def __init__(self, model=None):
        self._model = model

    @property
    def model(self):
        if self._model is None:
            self._model = build_model()
        return self._model

    def run(
        self,
        destino: str,
        fecha_inicio: str | None = None,
        fecha_fin: str | None = None,
        mensaje: str = "",
    ) -> ViajeOutput:
        entrada = ViajeInput(
            destino=destino,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            mensaje=mensaje,
        )
        datos = self._recolectar(entrada)
        texto = self._redactar(entrada, datos)
        return ViajeOutput(
            destino=entrada.destino,
            fecha_inicio=entrada.fecha_inicio,
            fecha_fin=entrada.fecha_fin,
            recomendaciones=texto,
            mensaje=texto,
        )

    def _recolectar(self, entrada: ViajeInput) -> dict:
        destino = entrada.destino
        fi, ff = entrada.fecha_inicio, entrada.fecha_fin
        return {
            "clima": buscar_clima(destino, fi, ff),
            "vuelos": buscar_vuelos(destino, fi, ff),
            "hoteles": buscar_hoteles(destino, fi, ff),
            "actividades": sugerir_actividades(destino, fi, ff),
        }

    def _redactar(self, entrada: ViajeInput, datos: dict) -> str:
        try:
            fechas = f"{entrada.fecha_inicio or 'sin fecha'} a {entrada.fecha_fin or 'sin fecha'}"
            consulta = entrada.mensaje or "(sin consulta adicional)"
            user_content = (
                f"Destino: {entrada.destino}\n"
                f"Fechas: {fechas}\n"
                f"Consulta del empleado: {consulta}\n"
                f"Datos de referencia: {json.dumps(datos, ensure_ascii=False)}"
            )
            response = self.model.generate(
                [
                    {"role": "system", "content": RECOMENDACION_SYSTEM},
                    {"role": "user", "content": user_content},
                ]
            )
            texto = (response.content or "").strip()
            if texto:
                return texto
            logger.warning("Modelo devolvio texto vacio, usando resumen basico")
        except Exception as exc:
            logger.warning("Redaccion con LLM fallo (%s), usando resumen basico", exc)
        return self._texto_basico(datos)

    @staticmethod
    def _texto_basico(datos: dict) -> str:
        clima = datos.get("clima", {}).get("resumen", "")
        vuelos = datos.get("vuelos", {}).get("opciones", [])
        hoteles = datos.get("hoteles", {}).get("opciones", [])
        actividades = datos.get("actividades", {}).get("actividades", [])
        partes = []
        if clima:
            partes.append(f"Clima: {clima}")
        if vuelos:
            mas_barato = min(vuelos, key=lambda v: v.get("precio_usd", 0))
            partes.append(
                "Vuelo sugerido: {} por {} USD ({} escalas).".format(
                    mas_barato.get("aerolinea"),
                    mas_barato.get("precio_usd"),
                    mas_barato.get("escalas"),
                )
            )
        if hoteles:
            mas_barato = min(hoteles, key=lambda h: h.get("precio_noche_usd", 0))
            partes.append(
                "Alojamiento economico: {} a {} USD por noche.".format(
                    mas_barato.get("nombre"),
                    mas_barato.get("precio_noche_usd"),
                )
            )
        if actividades:
            partes.append("Actividades: " + "; ".join(actividades) + ".")
        return " ".join(partes) if partes else (
            "Por ahora no tenemos datos de viaje para este destino."
        )
