import json

from aiohttp.web import Request, middleware
from pyinstrument import Profiler


def create_profiling_middleware(app_name: str):
    @middleware
    async def profiling_middleware(request: Request, handler):
        profiler: Profiler | None = None
        if request.headers.get(f"x-profile-{app_name}") is not None:
            profiler = Profiler(async_mode="enabled")
            profiler.start()

        response = await handler(request)
        if isinstance(profiler, Profiler):
            profiler.stop()
            response.text += "\n" + json.dumps(
                {"profile": profiler.output_text(unicode=True, color=True)}
            )

        return response

    return profiling_middleware
