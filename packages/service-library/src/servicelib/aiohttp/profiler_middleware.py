from aiohttp.web import Request, StreamResponse, middleware
from pyinstrument import Profiler

from .._utils_profiling_middleware import append_profile


def create_profiling_middleware(app_name: str):
    @middleware
    async def profiling_middleware(request: Request, handler):
        profiler: Profiler | None = None
        if request.headers.get(f"x-profile-{app_name}") is not None:
            profiler = Profiler(async_mode="enabled")
            profiler.start()

        response = await handler(request)

        if isinstance(profiler, Profiler):
            assert response.content_type == "application/json"
            stream_response = StreamResponse(
                status=response.status,
                reason=response.reason,
                headers=response.headers,
            )
            stream_response.content_type = "application/x-ndjson"
            await stream_response.prepare(request)
            await stream_response.write(response.body)
            profiler.stop()
            await stream_response.write(
                append_profile(
                    "", profiler.output_text(unicode=True, color=True)
                ).encode()
            )
            await stream_response.write_eof()
            return stream_response

        return response

    return profiling_middleware
