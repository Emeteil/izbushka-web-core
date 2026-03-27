from transport.base import BaseSubscriber
from typing import Any, Optional

class ComLinkSubscriber(BaseSubscriber):
    def __init__(self, commands: dict):
        super().__init__("com_link_rt")
        self._commands = commands

    def on_command(self, command: str, action: str, kwargs: dict) -> Optional[Any]:
        cmd = self._commands.get(command)
        if not cmd:
            return None
        method = getattr(cmd, action, None)
        if not method:
            return None
        return method(**kwargs)