import math
from typing import Any, Callable, Dict, Optional

from com_link_rt import DistanceCommand, MagnetometerCommand
from transport import TransportBus

MAGNETOMETER_STATUS = {
    MagnetometerCommand.STATUS_OK: "ok",
    MagnetometerCommand.STATUS_NOT_FOUND: "not_found",
    MagnetometerCommand.STATUS_OVERFLOW: "overflow",
    MagnetometerCommand.STATUS_NO_DATA: "no_data",
    MagnetometerCommand.STATUS_BUS_STUCK: "bus_stuck",
}


def format_magnetometer(data: Any) -> Optional[dict]:
    if not isinstance(data, dict) or not all(k in data for k in ("x", "y", "z", "status")):
        return None
    status = MAGNETOMETER_STATUS.get(data["status"], "unknown")
    scale = 100.0 / MagnetometerCommand.LSB_PER_GAUSS
    ut = [round(data[k] * scale, 2) for k in ("x", "y", "z")]
    has_field = status in ("ok", "overflow")
    heading = (math.degrees(math.atan2(ut[1], ut[0])) + 360.0) % 360.0 if has_field else None
    return {
        "status": status,
        "raw": [data["x"], data["y"], data["z"]],
        "ut": ut if has_field else None,
        "magnitude_ut": round(math.sqrt(sum(v * v for v in ut)), 2) if has_field else None,
        "heading_deg": round(heading, 1) if heading is not None else None,
    }


def format_distance(values: Any) -> Optional[dict]:
    if not isinstance(values, (list, tuple)):
        return None
    sensors = []
    for value in values:
        if value is None or value == DistanceCommand.SENSOR_ERROR:
            sensors.append({"mm": None, "status": "error"})
        elif value == DistanceCommand.NO_ECHO:
            sensors.append({"mm": None, "status": "far"})
        else:
            sensors.append({"mm": int(value), "status": "ok"})
    return {"sensors": sensors}


class SensorService:
    def __init__(self, transport_bus: TransportBus, com_link_commands: Optional[dict] = None):
        self._bus = transport_bus
        self._cmds: dict = com_link_commands or {}

    def get_millis(self) -> Optional[dict]:
        cached = self._cached_attr("millis", "last_data")
        if cached is not None:
            return {"millis": cached}
        raw = self._bus.execute("millis", "execute")
        return {"millis": raw} if raw is not None else None

    def get_distance(self) -> Optional[dict]:
        cached = self._cached_attr("distance", "last_data")
        if cached is not None:
            return format_distance(cached)
        return format_distance(self._bus.execute("distance", "execute"))

    def get_magnetometer(self) -> Optional[dict]:
        cached = self._cached_attr("magnetometer", "last_data")
        if cached is not None:
            return format_magnetometer(cached)
        return format_magnetometer(self._bus.execute("magnetometer", "execute"))

    def get_gps(self, timeout: float = 1.5) -> Optional[dict]:
        data = self._bus.execute("gps", "execute", timeout=timeout)
        return data if isinstance(data, dict) else None

    def last_gps(self) -> Optional[dict]:
        cmd = self._cmds.get("gps")
        return getattr(cmd, "last_data", None) if cmd is not None else None

    def get_all(self) -> Dict[str, Any]:
        getters: Dict[str, Callable[[], Optional[dict]]] = {
            "millis": self.get_millis,
            "distance": self.get_distance,
            "magnetometer": self.get_magnetometer,
            "gps": self.last_gps,
        }
        result: Dict[str, Any] = {}
        for name, getter in getters.items():
            value = getter()
            if value is not None:
                result[name] = value
        return result

    def subscriptions_status(self) -> Dict[str, bool]:
        return {
            name: bool(getattr(cmd, "is_subscribed", False))
            for name, cmd in self._cmds.items()
            if hasattr(cmd, "is_subscribed")
        }

    def _cached_attr(self, name: str, attr: str) -> Any:
        cmd = self._cmds.get(name)
        if cmd is None or not getattr(cmd, "is_subscribed", False):
            return None
        return getattr(cmd, attr, None)
