import json

from fastapi import FastAPI
from pyinstrument import Profiler
from starlette.requests import Request


def _generate_response_headers(content: bytes) -> list[tuple[bytes, bytes]]:
    headers: dict = dict()
    headers[b"content-length"] = str(len(content)).encode("utf8")
    headers[b"content-type"] = b"application/json"
    return list(headers.items())


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

        profiler = Profiler(async_mode="enabled")
        request: Request = Request(scope)
        headers = dict(request.headers)
        if self._profile_header_trigger in headers:
            headers.pop(self._profile_header_trigger)
            scope["headers"] = [
                (k.encode("utf8"), v.encode("utf8")) for k, v in headers.items()
            ]
            profiler.start()

        async def send_wrapper(message):
            if profiler.is_running:
                profiler.stop()
            if profiler.last_session:
                body: bytes = json.dumps(
                    {"profile": profiler.output_text(unicode=True, color=True)}
                ).encode("utf8")
                if message["type"] == "http.response.start":
                    message["headers"] = _generate_response_headers(body)
                elif message["type"] == "http.response.body":
                    message["body"] = body
            await send(message)

        await self._app(scope, receive, send_wrapper)
