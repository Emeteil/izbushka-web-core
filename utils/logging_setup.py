import json
import logging
import os
from datetime import datetime
from typing import Iterable

from .tracing import get_trace_id

_RESERVED_RECORD_KEYS = {
    "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
    "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
    "created", "msecs", "relativeCreated", "thread", "threadName",
    "processName", "process", "message", "asctime", "trace_id",
}

class TraceIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.trace_id = get_trace_id() or "-"
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.utcfromtimestamp(record.created).isoformat(timespec="milliseconds") + "Z",
            "level": record.levelname,
            "logger": record.name,
            "trace_id": getattr(record, "trace_id", "-"),
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key in _RESERVED_RECORD_KEYS or key.startswith("_"):
                continue
            payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


class HumanFormatter(logging.Formatter):
    DEFAULT_FORMAT = "%(asctime)s | %(levelname)-7s | %(trace_id)s | %(name)s | %(message)s"

    def __init__(self):
        super().__init__(self.DEFAULT_FORMAT)


def _build_handlers(log_filepath: str, json_format: bool) -> Iterable[logging.Handler]:
    formatter = JsonFormatter() if json_format else HumanFormatter()
    trace_filter = TraceIdFilter()

    file_handler = logging.FileHandler(log_filepath, encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.addFilter(trace_filter)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    stream_handler.addFilter(trace_filter)

    return [file_handler, stream_handler]


def setup_logging(log_dir: str = "logs", debug: bool = False, json_format: bool = False) -> str:
    os.makedirs(log_dir, exist_ok=True)
    log_filepath = os.path.join(log_dir, datetime.now().strftime("%Y-%m-%d_%H-%M-%S.log"))
    level = logging.DEBUG if debug else logging.INFO

    handlers = list(_build_handlers(log_filepath, json_format))

    root = logging.getLogger()
    root.setLevel(level)
    for handler in list(root.handlers):
        root.removeHandler(handler)
    for handler in handlers:
        root.addHandler(handler)

    for noisy in ("uvicorn.access",):
        logging.getLogger(noisy).propagate = True

    return log_filepath
