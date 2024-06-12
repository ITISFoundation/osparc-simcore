import contextvars
import json
from contextlib import contextmanager
from typing import Iterator

from pyinstrument import Profiler
from servicelib.mimetype_constants import (
    MIMETYPE_APPLICATION_JSON,
    MIMETYPE_APPLICATION_ND_JSON,
)

_request_profiler = contextvars.ContextVar("_request_profiler", default=None)


@contextmanager
def request_profiler() -> Iterator[Profiler | None]:
    """Context manager which temporarily removes request profiler from context"""
    _profiler = _request_profiler.get()
    if isinstance(_profiler, Profiler):
        try:
            _profiler.stop()
            _request_profiler.set(None)
            yield _profiler
        finally:
            _profiler.start()
            _request_profiler.set(_profiler)
    else:
        yield None


def append_profile(body: str, profile: str) -> str:
    try:
        json.loads(body)
        body += "\n" if not body.endswith("\n") else ""
    except json.decoder.JSONDecodeError:
        pass
    body += json.dumps({"profile": profile})
    return body


def check_response_headers(
    response_headers: dict[bytes, bytes]
) -> list[tuple[bytes, bytes]]:
    original_content_type: str = response_headers[b"content-type"].decode()
    assert original_content_type in {
        MIMETYPE_APPLICATION_ND_JSON,
        MIMETYPE_APPLICATION_JSON,
    }  # nosec
    headers: dict = {}
    headers[b"content-type"] = MIMETYPE_APPLICATION_ND_JSON.encode()
    return list(headers.items())
