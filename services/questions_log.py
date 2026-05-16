from __future__ import annotations

import json
import os
import threading
import uuid
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any


@dataclass
class QuestionEntry:
    id: str
    question: str
    answer: Optional[str]
    topic: Optional[str]
    source: str
    created_at: str
    extra: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        question: str,
        answer: Optional[str] = None,
        topic: Optional[str] = None,
        source: str = "voice",
        extra: Optional[Dict[str, Any]] = None,
    ) -> "QuestionEntry":
        return cls(
            id=uuid.uuid4().hex,
            question=question.strip(),
            answer=(answer or "").strip() or None,
            topic=(topic or "").strip() or None,
            source=source,
            created_at=datetime.now(timezone.utc).isoformat(),
            extra=extra or {},
        )


class QuestionsLogService:
    def __init__(self, file_path: str, max_entries: int = 5000) -> None:
        self._file_path = file_path
        self._max_entries = max_entries
        self._lock = threading.RLock()
        self._entries: List[QuestionEntry] = self._load()

    def _load(self) -> List[QuestionEntry]:
        if not os.path.exists(self._file_path):
            return []
        try:
            with open(self._file_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            return [QuestionEntry(**item) for item in raw]
        except Exception:
            return []

    def _persist(self) -> None:
        os.makedirs(os.path.dirname(self._file_path) or ".", exist_ok=True)
        tmp = self._file_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump([asdict(e) for e in self._entries], f, ensure_ascii=False, indent=2)
        os.replace(tmp, self._file_path)

    def add(
        self,
        question: str,
        answer: Optional[str] = None,
        topic: Optional[str] = None,
        source: str = "voice",
        extra: Optional[Dict[str, Any]] = None,
    ) -> QuestionEntry:
        entry = QuestionEntry.create(question, answer, topic, source, extra)
        with self._lock:
            self._entries.append(entry)
            if len(self._entries) > self._max_entries:
                self._entries = self._entries[-self._max_entries:]
            self._persist()
        return entry

    def recent(self, limit: int = 50, topic: Optional[str] = None) -> List[QuestionEntry]:
        with self._lock:
            items = self._entries
            if topic:
                items = [e for e in items if (e.topic or "").lower() == topic.lower()]
            return list(reversed(items[-limit:]))

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            total = len(self._entries)
            by_topic: Dict[str, int] = {}
            by_source: Dict[str, int] = {}
            for e in self._entries:
                if e.topic:
                    by_topic[e.topic] = by_topic.get(e.topic, 0) + 1
                by_source[e.source] = by_source.get(e.source, 0) + 1
            return {"total": total, "by_topic": by_topic, "by_source": by_source}

    def clear(self) -> int:
        with self._lock:
            removed = len(self._entries)
            self._entries = []
            self._persist()
        return removed
