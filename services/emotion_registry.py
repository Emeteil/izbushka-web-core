from pathlib import Path
from typing import Dict, List, Optional
import threading
import yaml

class EmotionNotFoundError(ValueError):
    pass

class EmotionRegistry:
    def __init__(self, items: List[dict], default: str):
        self._items: List[dict] = list(items)
        self._index: Dict[str, dict] = {e["id"]: e for e in self._items}
        if default not in self._index:
            raise EmotionNotFoundError(f"Default emotion {default!r} is not in registry")
        self._default = default
        self._current = default
        self._lock = threading.Lock()

    @classmethod
    def from_yaml(cls, path: str) -> "EmotionRegistry":
        with open(Path(path), "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        items = data.get("items") or []
        if not items:
            raise ValueError(f"Emotion config {path!r} contains no items")
        default = data.get("default") or items[0]["id"]
        return cls(items=items, default=default)

    @property
    def current(self) -> str:
        with self._lock:
            return self._current

    def set_current(self, emotion_id: str) -> dict:
        item = self._index.get(emotion_id)
        if item is None:
            raise EmotionNotFoundError(f"Unknown emotion: {emotion_id!r}")
        with self._lock:
            self._current = emotion_id
        return item

    def exists(self, emotion_id: str) -> bool:
        return emotion_id in self._index

    def get(self, emotion_id: str) -> Optional[dict]:
        return self._index.get(emotion_id)

    def ids(self) -> List[str]:
        return list(self._index.keys())

    def items(self) -> List[dict]:
        return list(self._items)