from typing import Any

from fastapi import FastAPI
from pyinstrument import Profiler
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON
from starlette.requests import Request

from .._utils_profiling_middleware import append_profile, check_response_headers


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

    def __init__(self, app: FastAPI):
        self._app: FastAPI = app
        self._profile_header_trigger: str = "x-profile"

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        profiler: Profiler | None = None
        request: Request = Request(scope)
        request_headers = dict(request.headers)
        response_headers: dict[bytes, bytes] = {}

        if request_headers.get(self._profile_header_trigger) is not None:
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
                    message["headers"] = check_response_headers(response_headers)
                elif message["type"] == "http.response.body":
                    if is_last_response(response_headers, message):
                        profiler.stop()
                        message["body"] = append_profile(
                            message["body"].decode(),
                            profiler.output_text(
                                unicode=True, color=True, show_all=True
                            ),
                        ).encode()
                    else:
                        message["more_body"] = True
            await send(message)

        await self._app(scope, receive, _send_wrapper)
