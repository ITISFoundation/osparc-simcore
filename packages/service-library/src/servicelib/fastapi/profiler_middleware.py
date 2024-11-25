from typing import Any, Final

from servicelib.aiohttp import status
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON
from starlette.requests import Request
from starlette.types import ASGIApp, Receive, Scope, Send

from ..utils_profiling_middleware import (
    _is_profiling,
    _profiler,
    append_profile,
    check_response_headers,
)


def is_last_response(response_headers: dict[bytes, bytes], message: dict[str, Any]):
    if (
        content_type := response_headers.get(b"content-type")
    ) and content_type == MIMETYPE_APPLICATION_JSON.encode():
        return True
    if (more_body := message.get("more_body")) is not None:
        return not more_body
    msg = "Could not determine if last response"
    raise RuntimeError(msg)


class ProfilerMiddleware:
    """Following
    https://www.starlette.io/middleware/#cleanup-and-error-handling
    https://www.starlette.io/middleware/#reusing-starlette-components
    https://fastapi.tiangolo.com/advanced/middleware/#advanced-middleware
    """

    def __init__(self, app: ASGIApp):
        self._app = app
        self._profile_header_trigger: Final[str] = "x-profile"

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        request: Request = Request(scope)
        request_headers = dict(request.headers)
        response_headers: dict[bytes, bytes] = {}

        if request_headers.get(self._profile_header_trigger) is None:
            await self._app(scope, receive, send)
            return

        if _profiler.is_running or (_profiler.last_session is not None):
            response = {
                "type": "http.response.start",
                "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "headers": [
                    (b"content-type", b"text/plain"),
                ],
            }
            await send(response)
            response_body = {
                "type": "http.response.body",
                "body": b"Profiler is already running. Only a single request can be profiled at any give time.",
            }
            await send(response_body)
            return

        try:
            request_headers.pop(self._profile_header_trigger)
            scope["headers"] = [
                (k.encode("utf8"), v.encode("utf8")) for k, v in request_headers.items()
            ]
            _profiler.start()
            _is_profiling.set(True)

            async def _send_wrapper(message):
                if _is_profiling.get():
                    nonlocal response_headers
                    if message["type"] == "http.response.start":
                        response_headers = dict(message.get("headers"))
                        message["headers"] = check_response_headers(response_headers)
                    elif message["type"] == "http.response.body":
                        if is_last_response(response_headers, message):
                            _profiler.stop()
                            profile_text = _profiler.output_text(
                                unicode=True, color=True, show_all=True
                            )
                            _profiler.reset()
                            message["body"] = append_profile(
                                message["body"].decode(), profile_text
                            ).encode()
                        else:
                            message["more_body"] = True
                await send(message)

            await self._app(scope, receive, _send_wrapper)

        finally:
            _profiler.reset()
