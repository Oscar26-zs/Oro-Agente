import json
import threading
from pathlib import Path

from ..utils.logger import get_logger

logger = get_logger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_STORE_PATH = REPO_ROOT / "data" / "viajes_store.json"


class ViajesStore:
    """Memoria persistente del orquestador.

    Guarda el contexto de cada solicitud creada via chat
    (solicitud_id -> empleado, destino, fechas) y si ya se entregaron
    las recomendaciones de viaje. Vive en un archivo JSON local; nunca
    toca la base de datos del sistema MVC.
    """

    def __init__(self, path: str | Path | None = None):
        self._path = Path(path) if path else DEFAULT_STORE_PATH
        self._lock = threading.Lock()
        self._data: dict = {"viajes": {}}
        self._load()

    def _load(self) -> None:
        try:
            if self._path.exists():
                data = json.loads(self._path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    self._data = data
            self._data.setdefault("viajes", {})
        except (OSError, ValueError) as exc:
            logger.warning(
                "No se pudo leer el store %s (%s); iniciando vacio", self._path, exc
            )
            self._data = {"viajes": {}}

    def _save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps(self._data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError as exc:
            logger.error("No se pudo guardar el store %s: %s", self._path, exc)

    def guardar_viaje(
        self,
        solicitud_id: str,
        empleado_id: str | None = None,
        destino: str | None = None,
        fecha_inicio: str | None = None,
        fecha_fin: str | None = None,
    ) -> None:
        """Registra o actualiza el contexto de una solicitud."""
        if not solicitud_id:
            return
        with self._lock:
            viajes: dict = self._data.setdefault("viajes", {})
            previo = viajes.get(solicitud_id, {})
            viajes[solicitud_id] = {
                "solicitud_id": solicitud_id,
                "empleado_id": (
                    str(empleado_id)
                    if empleado_id is not None
                    else previo.get("empleado_id")
                ),
                "destino": destino or previo.get("destino"),
                "fecha_inicio": fecha_inicio or previo.get("fecha_inicio"),
                "fecha_fin": fecha_fin or previo.get("fecha_fin"),
                "recomendaciones_entregadas": previo.get(
                    "recomendaciones_entregadas", False
                ),
            }
            self._save()

    def obtener(self, solicitud_id: str) -> dict | None:
        with self._lock:
            viaje = self._data.get("viajes", {}).get(solicitud_id)
            return dict(viaje) if viaje else None

    def viajes_pendientes_de_empleado(self, empleado_id: str | None) -> list[dict]:
        """Viajes del empleado cuyas recomendaciones aun no se entregan."""
        if empleado_id is None:
            return []
        emp = str(empleado_id)
        with self._lock:
            return [
                dict(viaje)
                for viaje in self._data.get("viajes", {}).values()
                if viaje.get("empleado_id") == emp
                and not viaje.get("recomendaciones_entregadas")
            ]

    def marcar_entregado(self, solicitud_id: str) -> None:
        with self._lock:
            viaje = self._data.get("viajes", {}).get(solicitud_id)
            if viaje is not None:
                viaje["recomendaciones_entregadas"] = True
                self._save()

    def eliminar(self, solicitud_id: str) -> bool:
        """Retira una entrada del contexto (ej. solicitudes que ya no existen)."""
        with self._lock:
            viajes = self._data.get("viajes", {})
            if solicitud_id in viajes:
                del viajes[solicitud_id]
                self._save()
                return True
            return False
