from typing import Any, Optional

from transport.base import BaseSubscriber
from transport.registry import TransportRegistry


class ConsoleLoggerSubscriber(BaseSubscriber):
    def __init__(self, log_level: str = "INFO", priority: int = 0):
        super().__init__("console_logger", priority=priority)
        self._level = log_level

    def on_command(self, command: str, action: str, kwargs: dict) -> Optional[Any]:
        args_str = ", ".join(f"{k}={v!r}" for k, v in kwargs.items())
        print(f"{self._level} {command}.{action}({args_str})")
        return None


@TransportRegistry.factory("console_logger")
def _build_console_logger(config: dict) -> ConsoleLoggerSubscriber:
    return ConsoleLoggerSubscriber(
        log_level=config.get("log_level", "INFO"),
        priority=config.get("priority", 0),
    )