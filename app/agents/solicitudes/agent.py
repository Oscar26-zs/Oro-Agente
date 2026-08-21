import json
import re

from ..base_agent import BaseAgent
from ..llm import build_model
from ...clients.vacaciones_api_client import VacacionesAPIClient
from ...utils.logger import get_logger
from .schemas import (
    IntencionSolicitud,
    SolicitudConsultarOutput,
    SolicitudCrearOutput,
    SolicitudOutput,
)
from .tools import consultar_estado_solicitud, crear_solicitud_vacaciones

logger = get_logger(__name__)

GUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)

ANALISIS_SYSTEM = (
    "Eres un analizador de mensajes de un sistema de vacaciones. El empleado escribe "
    "en lenguaje natural lo que quiere hacer (crear una solicitud de vacaciones o "
    "consultar el estado de una solicitud existente).\n"
    "Debes devolver UNICAMENTE un JSON valido con esta forma:\n"
    '{"accion": "crear" o "consultar", "solicitud_id": "GUID" o null, '
    '"empleado_id": "texto" o null, "fecha_inicio": "YYYY-MM-DD" o null, '
    '"fecha_fin": "YYYY-MM-DD" o null, "destino": "texto" o null}\n'
    "Reglas:\n"
    '- accion "crear": el empleado pide pedir/tomar/solicitar vacaciones con fechas. '
    "Convierte las fechas naturales al formato YYYY-MM-DD usando el anio 2026 si no lo menciona.\n"
    '- accion "consultar": el empleado pregunta por el estado/avance de una solicitud '
    "existente; entonces coloca su identificador (un GUID como "
    "3f2504e0-4f89-41d3-9a0c-0305e82c3301) en solicitud_id.\n"
    "- Si falta informacion clave (por ejemplo no hay fechas para crear), devuelve null "
    "en ese campo."
)


class AgenteSolicitudes(BaseAgent):
    def __init__(
        self,
        client: VacacionesAPIClient | None = None,
        model=None,
    ):
        self.client = client or VacacionesAPIClient()
        self._model = model

    @property
    def model(self):
        if self._model is None:
            self._model = build_model()
        return self._model

    def _analizar(self, mensaje: str) -> IntencionSolicitud:
        try:
            response = self.model.generate(
                [
                    {"role": "system", "content": ANALISIS_SYSTEM},
                    {"role": "user", "content": mensaje},
                ]
            )
            texto = (response.content or "").strip()
            inicio = texto.find("{")
            fin = texto.rfind("}")
            if inicio == -1 or fin == -1:
                raise ValueError("no JSON")
            datos = json.loads(texto[inicio : fin + 1])
            return IntencionSolicitud(
                accion=datos.get("accion", "consultar"),
                solicitud_id=datos.get("solicitud_id"),
                empleado_id=datos.get("empleado_id"),
                fecha_inicio=datos.get("fecha_inicio"),
                fecha_fin=datos.get("fecha_fin"),
                destino=datos.get("destino"),
            )
        except Exception as exc:
            logger.warning("Analisis LLM fallo (%s), usando heuristica", exc)
            return self._heuristica(mensaje)

    def _heuristica(self, mensaje: str) -> IntencionSolicitud:
        texto = mensaje.lower()
        if any(p in texto for p in ("consultar", "estado", "avance", "sigue", "como va")):
            m = GUID_RE.search(mensaje) or re.search(r"\b\d+\b", mensaje)
            return IntencionSolicitud(
                accion="consultar",
                solicitud_id=m.group(0) if m else None,
            )
        fechas = re.findall(r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}", mensaje)
        if fechas:
            f_inicio, f_fin = fechas[0], fechas[1] if len(fechas) > 1 else fechas[0]
            return IntencionSolicitud(
                accion="crear",
                fecha_inicio=self._normalizar_fecha(f_inicio),
                fecha_fin=self._normalizar_fecha(f_fin),
            )
        if "vacaciones" in texto or "solicitar" in texto:
            return IntencionSolicitud(accion="crear")
        return IntencionSolicitud(accion="consultar")

    @staticmethod
    def _normalizar_fecha(fecha: str) -> str:
        m = re.match(r"(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})", fecha)
        if not m:
            return fecha
        dia, mes, anio = m.groups()
        anio = f"20{anio}" if len(anio) == 2 else anio
        return f"{anio}-{mes.zfill(2)}-{dia.zfill(2)}"

    def _llamar(self, fn) -> dict:
        try:
            return fn()
        except RuntimeError as exc:
            logger.warning("Llamada a la API de vacaciones fallo: %s", exc)
            return {"error": str(exc)}

    @staticmethod
    def _mensaje_error(error: str, solicitud_id: str | None) -> str:
        if "404" in error or "no encontrada" in error.lower():
            referencia = (
                f"La solicitud {solicitud_id}" if solicitud_id else "Esa solicitud"
            )
            return (
                f"{referencia} no existe en el sistema de vacaciones (puede ser de "
                "una prueba anterior). Revisa el identificador o crea una nueva "
                "solicitud."
            )
        return error

    def run(self, mensaje: str, empleado_id: int | str | None = None) -> SolicitudOutput:
        intencion = self._analizar(mensaje)
        identificador = intencion.empleado_id or (
            str(empleado_id) if empleado_id is not None else None
        )
        if identificador is not None:
            intencion.empleado_id = str(identificador)

        if intencion.accion == "consultar" and intencion.solicitud_id:
            data = self._llamar(
                lambda: consultar_estado_solicitud(
                    intencion.solicitud_id, client=self.client
                )
            )
            if "error" in data:
                return SolicitudConsultarOutput(
                    accion="consultar",
                    solicitud_id=data.get("solicitud_id") or intencion.solicitud_id,
                    estado="error",
                    mensaje=self._mensaje_error(data["error"], intencion.solicitud_id),
                )
            return SolicitudConsultarOutput(
                accion="consultar",
                solicitud_id=data.get("solicitud_id"),
                estado=data.get("estado", "desconocido"),
                mensaje=data.get(
                    "mensaje",
                    f"La solicitud {intencion.solicitud_id} figura con estado "
                    f"{data.get('estado', 'desconocido')}.",
                ),
            )

        if not intencion.fecha_inicio or not intencion.fecha_fin:
            return SolicitudOutput(
                accion="crear",
                estado="incompleta",
                mensaje=(
                    "Para crear la solicitud necesito que me indiques el destino y las "
                    "fechas exactas de tus vacaciones (por ejemplo: del 10 de septiembre "
                    "al 15 de septiembre)."
                ),
            )

        if not intencion.empleado_id:
            return SolicitudOutput(
                accion="crear",
                estado="incompleta",
                mensaje="No tengo el identificador del empleado para crear la solicitud.",
            )

        data = self._llamar(
            lambda: crear_solicitud_vacaciones(
                empleado_id=intencion.empleado_id,
                fecha_inicio=intencion.fecha_inicio,
                fecha_fin=intencion.fecha_fin,
                destino=intencion.destino,
                client=self.client,
            )
        )
        if "error" in data:
            return SolicitudCrearOutput(
                accion="crear",
                estado="error",
                fecha_inicio=intencion.fecha_inicio,
                fecha_fin=intencion.fecha_fin,
                destino=intencion.destino,
                mensaje=data["error"],
            )
        return SolicitudCrearOutput(
            accion="crear",
            solicitud_id=data.get("solicitud_id"),
            estado=data.get("estado", "desconocido"),
            fecha_inicio=intencion.fecha_inicio,
            fecha_fin=intencion.fecha_fin,
            destino=intencion.destino,
            mensaje=data.get(
                "mensaje",
                f"Solicitud creada con estado {data.get('estado', 'desconocido')}.",
            ),
        )