from abc import ABC, abstractmethod
from typing import Any, Optional

class BaseSubscriber(ABC):
    def __init__(self, name: str):
        self.name = name
        self.enabled = True

    @abstractmethod
    def on_command(self, command: str, action: str, kwargs: dict) -> Optional[Any]:
        pass

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass