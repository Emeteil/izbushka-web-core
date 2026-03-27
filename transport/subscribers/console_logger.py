from transport.base import BaseSubscriber
from typing import Any, Optional

class ConsoleLoggerSubscriber(BaseSubscriber):
    def __init__(self, log_level: str = "INFO"):
        super().__init__("console_logger")
        self._level = log_level

    def on_command(self, command: str, action: str, kwargs: dict) -> Optional[Any]:
        args_str = ", ".join(f"{k}={v!r}" for k, v in kwargs.items())
        print(f"{self._level} {command}.{action}({args_str})")
        return None