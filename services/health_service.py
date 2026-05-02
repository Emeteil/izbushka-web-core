from time import time
from typing import Any, Dict, Optional

from transport import TransportBus

from .sensor_service import SensorService

class HealthService:
    def __init__(
        self,
        transport_bus: TransportBus,
        sensor_service: SensorService,
        com_link_connection: Any,
        com_link_port: Optional[str],
        started_at: float,
    ):
        self._bus = transport_bus
        self._sensors = sensor_service
        self._com_link = com_link_connection
        self._com_link_port = com_link_port
        self._started_at = started_at

    def snapshot(self) -> Dict[str, Any]:
        return {
            "uptime_seconds": round(time() - self._started_at, 2),
            "transport": self._transport_section(),
            "comlink": self._comlink_section(),
            "sensors": self._sensors_section(),
            "voice": self._voice_section(),
            "camera": self._camera_section(),
        }

    def _transport_section(self) -> Dict[str, Any]:
        return {
            "active": self._bus.has_active(),
            "subscribers": self._bus.status(),
        }

    def _comlink_section(self) -> Dict[str, Any]:
        connection = self._com_link
        is_open = bool(connection and getattr(connection, "ser", None) and connection.ser.is_open)
        vl = self._bus.get("virtual_link")
        return {
            "hardware_connected": is_open,
            "virtual_connected": bool(vl is not None and vl.enabled and getattr(vl, "is_connected", False)),
            "port": self._com_link_port,
        }

    def _sensors_section(self) -> Dict[str, Any]:
        return {
            "subscriptions": self._sensors.subscriptions_status(),
            "last_values": self._sensors.get_all() if self._bus.has_active() else {},
        }

    @staticmethod
    def _voice_section() -> Dict[str, Any]:
        try:
            from api.voice_link import voice_state
            return voice_state.to_dict()
        except Exception:
            return {"connected": False, "status": "unknown"}

    @staticmethod
    def _camera_section() -> Dict[str, Any]:
        try:
            from api import webcam_api
            frame_age = round(time() - webcam_api.last_frame_time, 3) if webcam_api.last_frame_time else None
            return {
                "quality": webcam_api.video_quality.get("quality"),
                "width": webcam_api.video_quality.get("width"),
                "height": webcam_api.video_quality.get("height"),
                "fps": webcam_api.video_quality.get("fps"),
                "auto_adjust": webcam_api.video_quality.get("auto_adjust"),
                "last_frame_age_seconds": frame_age,
            }
        except Exception:
            return {"available": False}