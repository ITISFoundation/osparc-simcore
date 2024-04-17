import json
from typing import Any

from fastapi import FastAPI
from pyinstrument import Profiler
from starlette.requests import Request


def _check_response_headers(
    response_headers: dict[bytes, bytes]
) -> list[tuple[bytes, bytes]]:
    original_content_type: str = response_headers[b"content-type"].decode()
    assert original_content_type in {
        "application/x-ndjson",
        "application/json",
    }  # nosec
    headers: dict = {}
    headers[b"content-type"] = b"application/x-ndjson"
    return list(headers.items())


def _append_profile(body: str, profile: str) -> str:
    try:
        json.loads(body)
        body += "\n" if not body.endswith("\n") else ""
    except json.decoder.JSONDecodeError:
        pass
    body += json.dumps({"profile": profile})
    return body


def is_last_response(response_headers: dict[bytes, bytes], message: dict[str, Any]):
    if (
        content_type := response_headers.get(b"content-type")
    ) and content_type == b"application/json":
        return True
    if (more_body := message.get("more_body")) is not None:
        return not more_body
    msg = "Could not determine if last response"
    raise RuntimeError(msg)


class ApiServerProfilerMiddleware:
    """Following
    https://www.starlette.io/middleware/#cleanup-and-error-handling
    https://www.starlette.io/middleware/#reusing-starlette-components
    https://fastapi.tiangolo.com/advanced/middleware/#advanced-middleware
    """

    def __init__(self, app: FastAPI):
        self._app: FastAPI = app
        self._profile_header_trigger: str = "x-profile-api-server"

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        profiler: Profiler | None = None
        request: Request = Request(scope)
        request_headers = dict(request.headers)
        response_headers: dict[bytes, bytes] = {}

        if request_headers.get(self._profile_header_trigger) == "true":
            request_headers.pop(self._profile_header_trigger)
            scope["headers"] = [
                (k.encode("utf8"), v.encode("utf8")) for k, v in request_headers.items()
            ]
            profiler = Profiler(async_mode="enabled")
            profiler.start()

        async def _send_wrapper(message):
            if isinstance(profiler, Profiler):
                nonlocal response_headers
                if message["type"] == "http.response.start":
                    response_headers = dict(message.get("headers"))
                    message["headers"] = _check_response_headers(response_headers)
                elif message["type"] == "http.response.body":
                    if is_last_response(response_headers, message):
                        profiler.stop()
                        message["body"] = _append_profile(
                            message["body"].decode(),
                            profiler.output_text(unicode=True, color=True),
                        ).encode()
                    else:
                        message["more_body"] = True
            await send(message)

        await self._app(scope, receive, _send_wrapper)
