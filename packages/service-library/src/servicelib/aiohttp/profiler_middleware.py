from aiohttp.web import HTTPInternalServerError, Request, StreamResponse, middleware
from pyinstrument import Profiler
from servicelib.mimetype_constants import (
    MIMETYPE_APPLICATION_JSON,
    MIMETYPE_APPLICATION_ND_JSON,
)

from .._utils_profiling_middleware import append_profile


@middleware
async def profiling_middleware(request: Request, handler):
    profiler: Profiler | None = None
    if request.headers.get("x-profile") is not None:
        profiler = Profiler(async_mode="enabled")
        profiler.start()

    response = await handler(request)

    if profiler is None:
        return response
    if response.content_type != MIMETYPE_APPLICATION_JSON:
        raise HTTPInternalServerError(
            reason=f"Profiling middleware is not compatible with {response.content_type=}",
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
    profiler.stop()
    await stream_response.write(
        append_profile(
            "\n", profiler.output_text(unicode=True, color=True, show_all=True)
        ).encode()
    )
    await stream_response.write_eof()
    return stream_response
