from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any, TypeAlias

from aiohttp import web

# Taken from aiohttp.web_middlewares import _Handler, _Middleware
Handler: TypeAlias = Callable[[web.Request], Awaitable[web.StreamResponse]]
HandlerAnyReturn: TypeAlias = Callable[[web.Request], Awaitable[Any]]
Middleware: TypeAlias = Callable[[web.Request, Handler], Awaitable[web.StreamResponse]]


CleanupContextFunc: TypeAlias = Callable[[web.Application], AsyncIterator[None]]
