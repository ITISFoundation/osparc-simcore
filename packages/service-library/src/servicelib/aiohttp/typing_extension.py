from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any, TypeAlias

from aiohttp import web
from aiohttp.typedefs import Handler

try:
    from aiohttp.typedefs import Middleware
except ImportError:
    # For older versions
    # Taken from aiohttp.web_middlewares import _Handler, _Middleware
    Middleware: TypeAlias = Callable[  # type: ignore[no-redef]
        [web.Request, Handler], Awaitable[web.StreamResponse]
    ]


__all__: tuple[str, ...] = (
    "Handler",
    "Middleware",
)


HandlerAnyReturn: TypeAlias = Callable[[web.Request], Awaitable[Any]]
CleanupContextFunc: TypeAlias = Callable[[web.Application], AsyncIterator[None]]
