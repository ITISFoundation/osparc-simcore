from collections.abc import Awaitable, Callable
from typing import Any, TypeAlias

from aiohttp.web import Request, StreamResponse

# Taken from aiohttp.web_middlewares import _Handler, _Middleware
Handler: TypeAlias = Callable[[Request], Awaitable[StreamResponse]]
HandlerAnyReturn: TypeAlias = Callable[[Request], Awaitable[Any]]
Middleware: TypeAlias = Callable[[Request, Handler], Awaitable[StreamResponse]]
