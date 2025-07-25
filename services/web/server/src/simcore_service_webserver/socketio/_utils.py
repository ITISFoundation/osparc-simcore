import inspect
from collections.abc import Awaitable, Callable
from functools import wraps
from types import ModuleType
from typing import Any

from aiohttp import web
from socketio import AsyncServer  # type: ignore[import-untyped]

APP_CLIENT_SOCKET_DECORATED_HANDLERS_KEY = f"{__name__}.socketio_handlers"
APP_CLIENT_SOCKET_SERVER_KEY = f"{__name__}.socketio_socketio"


def get_socket_server(app: web.Application) -> AsyncServer:
    return app[APP_CLIENT_SOCKET_SERVER_KEY]


# The socket ID that was assigned to the client
SocketID = str

# The environ argument is a dictionary in standard WSGI format containing the request information, including HTTP headers
EnvironDict = dict[str, Any]

# Connect event
SocketioConnectEventHandler = Callable[
    [SocketID, EnvironDict, web.Application], Awaitable[None]
]

# Disconnect event
SocketioDisconnectEventHandler = Callable[[SocketID, web.Application], Awaitable[None]]

# Event
AnyData = Any
SocketioEventHandler = Callable[[SocketID, AnyData, web.Application], Awaitable[None]]

_socketio_handlers_registry: list[
    (
        SocketioEventHandler
        | SocketioConnectEventHandler
        | SocketioDisconnectEventHandler
    )
] = []


def _socket_io_handler(app: web.Application):
    """This decorator allows passing additional paramters to python-socketio compatible handlers.

    i.e. python-socketio handler expect functions of type `async def function(sid, *args, **kwargs)`

    This allows to create a function of type `async def function(sid, *args, **kwargs, app: web.Application)
    """

    def decorator(func):
        @wraps(func)
        async def wrapped(*args, **kwargs):
            return await func(*args, **kwargs, app=app)

        return wrapped

    return decorator


def _has_socket_io_handler_signature(fun: Callable) -> bool:
    # last parameter is web.Application?
    last_parameter = list(inspect.signature(fun).parameters.values())[-1]
    is_web_app: bool = last_parameter.annotation == web.Application
    return is_web_app


def register_socketio_handlers(app: web.Application, module: ModuleType):
    sio = get_socket_server(app)
    member_fcts = [
        fct for fct in _socketio_handlers_registry if inspect.getmodule(fct) == module
    ]
    # convert handler
    partial_fcts = [
        _socket_io_handler(app)(func_handler) for func_handler in member_fcts
    ]
    app[APP_CLIENT_SOCKET_DECORATED_HANDLERS_KEY] = partial_fcts

    # register the fcts
    for func in partial_fcts:
        sio.on(func.__name__, handler=func)


def register_socketio_handler(func: Callable) -> Callable:
    """This decorator appends handlers to a registry if they fit certain rules

    Arguments:
        func the function to call

    Raises:
        SyntaxError if invalid handler

    Returns:
        the function to call
    """

    is_handler = (
        inspect.isfunction(func)
        and _has_socket_io_handler_signature(func)
        and inspect.iscoroutinefunction(func)
    )
    if is_handler:
        _socketio_handlers_registry.append(func)
    else:
        msg = "the function shall be of type fct(*args, app: web.Application"
        raise SyntaxError(msg)
    return func
