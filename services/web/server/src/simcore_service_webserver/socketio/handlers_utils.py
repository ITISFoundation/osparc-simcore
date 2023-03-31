import inspect
from functools import wraps
from types import ModuleType
from typing import Any, Awaitable, Callable, Union

from aiohttp import web

from .server import APP_CLIENT_SOCKET_DECORATED_HANDLERS_KEY, get_socket_server

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
    Union[
        SocketioEventHandler,
        SocketioConnectEventHandler,
        SocketioDisconnectEventHandler,
    ]
] = []


def socket_io_handler(app: web.Application):
    """this decorator allows passing additional paramters to python-socketio compatible handlers.
    I.e. python-socketio handler expect functions of type `async def function(sid, *args, **kwargs)`
    This allows to create a function of type `async def function(sid, *args, **kwargs, app: web.Application)
    """

    def decorator(func):
        @wraps(func)
        async def wrapped(*args, **kwargs):
            return await func(*args, **kwargs, app=app)

        return wrapped

    return decorator


def has_socket_io_handler_signature(fun) -> bool:
    # last parameter is web.Application
    return (
        list(inspect.signature(fun).parameters.values())[-1].annotation
        == web.Application
    )


def register_handlers(app: web.Application, module: ModuleType):
    sio = get_socket_server(app)
    member_fcts = [
        fct for fct in _socketio_handlers_registry if inspect.getmodule(fct) == module
    ]
    # convert handler
    partial_fcts = [
        socket_io_handler(app)(func_handler) for func_handler in member_fcts
    ]
    app[APP_CLIENT_SOCKET_DECORATED_HANDLERS_KEY] = partial_fcts

    # register the fcts
    for func in partial_fcts:
        sio.on(func.__name__, handler=func)


def register_socketio_handler(func: Callable) -> Callable:
    """this decorator appends handlers to a registry if they fit certain rules

    :param func: the function to call
    :type func: callable
    :return: the function to call
    :rtype: callable
    """
    is_handler = (
        inspect.isfunction(func)
        and has_socket_io_handler_signature(func)
        and inspect.iscoroutinefunction(func)
    )
    if is_handler:
        _socketio_handlers_registry.append(func)
    else:
        raise SyntaxError(
            "the function shall be of type fct(*args, app: web.Application"
        )
    return func
