from typing import List, Optional, Any
from .base import BaseSubscriber
import threading
import logging
import time

from utils.tracing import trace_scope, get_trace_id

logger = logging.getLogger("transport")


class TransportBus:
    def __init__(self):
        self._subscribers: List[BaseSubscriber] = []
        self._lock = threading.Lock()

    def add(self, subscriber: BaseSubscriber) -> None:
        with self._lock:
            self._subscribers.append(subscriber)
            self._subscribers.sort(key=lambda s: s.priority)
        subscriber.start()
        logger.info(f"[TransportBus] + {subscriber.name} (priority={subscriber.priority})")

    def remove(self, name: str) -> None:
        target: Optional[BaseSubscriber] = None
        with self._lock:
            for sub in self._subscribers:
                if sub.name == name:
                    target = sub
                    self._subscribers.remove(sub)
                    break
        if target is not None:
            target.stop()
            logger.info(f"[TransportBus] - {name}")

    def get(self, name: str) -> Optional[BaseSubscriber]:
        with self._lock:
            return next((s for s in self._subscribers if s.name == name), None)

    def execute(self, command: str, action: str, **kwargs) -> Optional[Any]:
        with self._lock:
            chain = list(self._subscribers)

        with trace_scope(get_trace_id()):
            started = time.perf_counter()
            logger.debug(
                "transport.execute.start",
                extra={"command": command, "action": action, "kwargs": kwargs},
            )

            produced_result = False
            first_result: Any = None
            handled_by: Optional[str] = None

            for sub in chain:
                if not sub.enabled or not sub.can_handle(command, action):
                    continue
                try:
                    result = sub.on_command(command, action, kwargs)
                except Exception as e:
                    logger.error(
                        "transport.subscriber.error",
                        extra={"subscriber": sub.name, "command": command, "action": action, "error": str(e)},
                    )
                    continue
                if result is not None and not produced_result:
                    first_result = result
                    produced_result = True
                    handled_by = sub.name

            latency_ms = round((time.perf_counter() - started) * 1000, 3)
            logger.info(
                "transport.execute.end",
                extra={
                    "command": command,
                    "action": action,
                    "handled_by": handled_by,
                    "latency_ms": latency_ms,
                    "produced_result": produced_result,
                },
            )
            return first_result

    def has_active(self) -> bool:
        with self._lock:
            return any(s.enabled for s in self._subscribers)

    def status(self) -> List[dict]:
        with self._lock:
            return [s.health() for s in self._subscribers]

    def stop_all(self) -> None:
        with self._lock:
            chain = list(self._subscribers)
        for sub in chain:
            try:
                sub.stop()
            except Exception as e:
                logger.error(f"[TransportBus] stop {sub.name}: {e}")
