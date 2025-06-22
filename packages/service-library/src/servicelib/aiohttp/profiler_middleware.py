from aiohttp.web import HTTPInternalServerError, Request, StreamResponse, middleware
from servicelib.mimetype_constants import (
    MIMETYPE_APPLICATION_JSON,
    MIMETYPE_APPLICATION_ND_JSON,
)

from ..utils_profiling_middleware import _is_profiling, _profiler, append_profile


@middleware
async def profiling_middleware(request: Request, handler):
    if request.headers.get("x-profile") is not None:
        try:
            if _profiler.is_running or (_profiler.last_session is not None):
                raise HTTPInternalServerError(
                    text="Profiler is already running. Only a single request can be profiled at any given time.",
                    headers={},
                )
            _profiler.reset()
            _is_profiling.set(True)

            with _profiler:
                response = await handler(request)

            if response.content_type != MIMETYPE_APPLICATION_JSON:
                raise HTTPInternalServerError(
                    text=f"Profiling middleware is not compatible with {response.content_type=}",
                    headers={},
                )

            stream_response = StreamResponse(
                status=response.status,
                reason=response.reason,
                headers=response.headers,
            )
            stream_response.content_type = MIMETYPE_APPLICATION_ND_JSON
            await stream_response.prepare(request)
            await stream_response.write(response.body)
            await stream_response.write(
                append_profile(
                    "\n", _profiler.output_text(unicode=True, color=True, show_all=True)
                ).encode()
            )
            await stream_response.write_eof()
        finally:
            _profiler.reset()
        return stream_response

    return await handler(request)
