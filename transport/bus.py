from typing import List, Optional, Any
from .base import BaseSubscriber
import threading
import logging

logger = logging.getLogger("transport")

class TransportBus:
    def __init__(self):
        self._subscribers: List[BaseSubscriber] = []
        self._lock = threading.Lock()

    def add(self, subscriber: BaseSubscriber) -> None:
        with self._lock:
            self._subscribers.append(subscriber)
            subscriber.start()
            logger.info(f"[TransportBus] + {subscriber.name}")

    def remove(self, name: str) -> None:
        with self._lock:
            for sub in self._subscribers:
                if sub.name == name:
                    sub.stop()
                    self._subscribers.remove(sub)
                    logger.info(f"[TransportBus] - {name}")
                    return

    def execute(self, command: str, action: str, **kwargs) -> Optional[Any]:
        result = None
        with self._lock:
            subs = list(self._subscribers)
        for sub in subs:
            if not sub.enabled:
                continue
            try:
                r = sub.on_command(command, action, kwargs)
                if r is not None and result is None:
                    result = r
            except Exception as e:
                logger.error(f"[TransportBus] {sub.name} error: {e}")
        return result

    def has_active(self) -> bool:
        with self._lock:
            return any(s.enabled for s in self._subscribers)

    def get(self, name: str) -> Optional[BaseSubscriber]:
        with self._lock:
            for sub in self._subscribers:
                if sub.name == name:
                    return sub
        return None

    def status(self) -> List[dict]:
        with self._lock:
            return [{"name": s.name, "enabled": s.enabled}
                    for s in self._subscribers]

    def stop_all(self) -> None:
        with self._lock:
            for sub in self._subscribers:
                try:
                    sub.stop()
                except Exception as e:
                    logger.error(f"[TransportBus] stop {sub.name}: {e}")