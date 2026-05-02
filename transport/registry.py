from typing import Callable, Dict, List
from .base import BaseSubscriber

class TransportError(Exception):
    pass

TransportFactory = Callable[[dict], BaseSubscriber]

class TransportRegistry:
    _factories: Dict[str, TransportFactory] = {}

    @classmethod
    def register(cls, name: str, factory: TransportFactory) -> None:
        cls._factories[name] = factory

    @classmethod
    def factory(cls, name: str):
        def decorator(fn: TransportFactory) -> TransportFactory:
            cls.register(name, fn)
            return fn
        return decorator

    @classmethod
    def build(cls, name: str, config: dict) -> BaseSubscriber:
        factory = cls._factories.get(name)
        if factory is None:
            raise TransportError(
                f"Unknown transport plugin: {name!r}. "
                f"Available: {sorted(cls._factories.keys())}"
            )
        return factory(config)

    @classmethod
    def available(cls) -> List[str]:
        return list(cls._factories.keys())

    @classmethod
    def has(cls, name: str) -> bool:
        return name in cls._factories
