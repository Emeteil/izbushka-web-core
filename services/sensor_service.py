from typing import Any, Callable, Dict, Optional

from transport import TransportBus

class SensorService:
    def __init__(self, transport_bus: TransportBus, com_link_commands: Optional[dict] = None):
        self._bus = transport_bus
        self._cmds: dict = com_link_commands or {}

    def get_distance(self) -> Optional[dict]:
        cached = self._cached_attr("distance", "last_distance")
        if cached is not None:
            return {"distance_cm": cached}
        raw = self._bus.execute("distance", "execute")
        return {"distance_cm": raw} if raw is not None else None

    def get_millis(self) -> Optional[dict]:
        cached = self._cached_attr("millis", "last_data")
        if cached is not None:
            return {"millis": cached}
        raw = self._bus.execute("millis", "execute")
        return {"millis": raw} if raw is not None else None

    def get_gyro(self) -> Optional[dict]:
        cmd = self._cmds.get("gyro")
        cached = self._cached_attr("gyro", "last_data")
        if cmd is not None and cached is not None:
            return self._format_gyro(cmd, cached)

        raw = self._bus.execute("gyro", "execute")
        if raw is None:
            return None
        if isinstance(raw, dict) and "accel" in raw:
            return raw
        if cmd is None:
            return None
        return self._format_gyro(cmd, raw)

    def get_all(self) -> Dict[str, Any]:
        getters: Dict[str, Callable[[], Optional[dict]]] = {
            "distance": self.get_distance,
            "gyro": self.get_gyro,
            "millis": self.get_millis,
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

    @staticmethod
    def _format_gyro(cmd: Any, data: Any) -> dict:
        return {
            "accel": cmd.get_acceleration(data),
            "gyro": cmd.get_rotation(data),
            "temperature": cmd.get_temperature(data),
        }