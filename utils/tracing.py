from contextlib import contextmanager
from contextvars import ContextVar
from typing import Optional
import secrets

_TRACE_ID: ContextVar[Optional[str]] = ContextVar("trace_id", default=None)

def new_trace_id() -> str:
    return secrets.token_hex(8)

def get_trace_id() -> Optional[str]:
    return _TRACE_ID.get()

def set_trace_id(trace_id: Optional[str]) -> None:
    _TRACE_ID.set(trace_id)

@contextmanager
def trace_scope(trace_id: Optional[str] = None):
    token = _TRACE_ID.set(trace_id or new_trace_id())
    try:
        yield _TRACE_ID.get()
    finally:
        _TRACE_ID.reset(token)