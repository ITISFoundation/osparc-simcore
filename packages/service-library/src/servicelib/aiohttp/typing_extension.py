from typing import Awaitable, Callable

from aiohttp.web import Request, StreamResponse

# Taken from aiohttp.web_middlewares import _Handler, _Middleware
Handler = Callable[[Request], Awaitable[StreamResponse]]
Middleware = Callable[[Request, Handler], Awaitable[StreamResponse]]
