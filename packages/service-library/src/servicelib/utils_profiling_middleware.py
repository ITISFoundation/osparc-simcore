import contextvars
import json
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Final

from common_library.json_serialization import json_dumps, json_loads
from pyinstrument import Profiler

from .mimetype_constants import MIMETYPE_APPLICATION_JSON, MIMETYPE_APPLICATION_ND_JSON

_UNSET: Final = None

_profiler = Profiler(async_mode="enabled")
_is_profiling = contextvars.ContextVar("_is_profiling", default=False)


def is_profiling() -> bool:
    return _is_profiling.get()


@contextmanager
def profile_context(enable: bool | None = _UNSET) -> Iterator[None]:
    """Context manager which temporarily removes request profiler from context"""
    if enable is _UNSET:
        enable = _is_profiling.get()
    if enable:
        try:
            _profiler.start()
            yield
        finally:
            _profiler.stop()
    else:
        yield None


@contextmanager
def dont_profile() -> Iterator[None]:
    if _is_profiling.get():
        try:
            _profiler.stop()
            yield
        finally:
            _profiler.start()
    else:
        yield


def append_profile(body: str, profile_text: str) -> str:
    try:
        json_loads(body)
        body += "\n" if not body.endswith("\n") else ""
    except json.decoder.JSONDecodeError:
        pass
    body += json_dumps({"profile": profile_text})
    return body


def check_response_headers(
    response_headers: dict[bytes, bytes]
) -> list[tuple[bytes, bytes]]:
    original_content_type: str = response_headers[b"content-type"].decode()
    assert original_content_type in {  # nosec
        MIMETYPE_APPLICATION_ND_JSON,
        MIMETYPE_APPLICATION_JSON,
    }
    headers: dict = {}
    headers[b"content-type"] = MIMETYPE_APPLICATION_ND_JSON.encode()
    return list(headers.items())
