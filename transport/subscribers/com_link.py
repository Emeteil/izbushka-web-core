from typing import Any, Optional

from transport.base import BaseSubscriber
from transport.registry import TransportRegistry


class ComLinkSubscriber(BaseSubscriber):
    def __init__(self, commands: dict, priority: int = 10):
        super().__init__("com_link_rt", priority=priority)
        self._commands = commands

    def can_handle(self, command: str, action: str) -> bool:
        return command in self._commands

    def on_command(self, command: str, action: str, kwargs: dict) -> Optional[Any]:
        cmd = self._commands.get(command)
        if cmd is None:
            return None
        method = getattr(cmd, action, None)
        if method is None:
            return None
        return method(**kwargs)

    def health(self) -> dict:
        base = super().health()
        base["commands"] = sorted(self._commands.keys())
        return base


@TransportRegistry.factory("com_link_rt")
def _build_com_link(config: dict) -> ComLinkSubscriber:
    commands = config.get("commands")
    if commands is None:
        raise ValueError("com_link_rt transport requires 'commands' in config")
    return ComLinkSubscriber(
        commands=commands,
        priority=config.get("priority", 10),
    )
