import contextvars
import json

from servicelib.mimetype_constants import (
    MIMETYPE_APPLICATION_JSON,
    MIMETYPE_APPLICATION_ND_JSON,
)

request_profiler = contextvars.ContextVar("request_profiler", default=None)


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
