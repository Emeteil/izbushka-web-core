from abc import ABC, abstractmethod
from typing import Any, Optional

DEFAULT_PRIORITY = 100


class BaseSubscriber(ABC):
    def __init__(self, name: str, priority: int = DEFAULT_PRIORITY):
        self.name = name
        self.priority = priority
        self.enabled = True

    def can_handle(self, command: str, action: str) -> bool:
        return True

    @abstractmethod
    def on_command(self, command: str, action: str, kwargs: dict) -> Optional[Any]:
        ...

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def health(self) -> dict:
        return {"name": self.name, "enabled": self.enabled, "priority": self.priority}
