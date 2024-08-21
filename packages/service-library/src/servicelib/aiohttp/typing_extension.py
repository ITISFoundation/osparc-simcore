from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any, TypeAlias

from aiohttp import web

try:
    import aiohttp.typedefs

    assert aiohttp.typedefs is not None  # nosec
    has_typedefs = True
except ImportError:
    has_typedefs = False


if has_typedefs:
    from aiohttp.typedefs import Handler, Middleware

else:
    # For older versions
    # Taken from aiohttp.web_middlewares import _Handler, _Middleware

    Handler: TypeAlias = Callable[[web.Request], Awaitable[web.StreamResponse]]  # type: ignore[no-redef, misc]
    Middleware: TypeAlias = Callable[  # type: ignore[no-redef]
        [web.Request, Handler], Awaitable[web.StreamResponse]
    ]


__all__: tuple[str, ...] = (
    "Handler",
    "Middleware",
)


HandlerAnyReturn: TypeAlias = Callable[[web.Request], Awaitable[Any]]
CleanupContextFunc: TypeAlias = Callable[[web.Application], AsyncIterator[None]]
