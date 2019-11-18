import inspect
from functools import wraps
from types import ModuleType

from aiohttp import web

from .config import APP_CLIENT_SOCKET_DECORATED_HANDLERS_KEY, get_socket_server


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
    return list(inspect.signature(fun).parameters.values())[-1].annotation == web.Application

def register_handlers(app: web.Application, module: ModuleType):
    sio = get_socket_server(app)
    predicate = lambda obj: inspect.isfunction(obj) and \
                has_socket_io_handler_signature(obj) and \
                inspect.iscoroutinefunction(obj) and \
                    inspect.getmodule(obj) == module
    member_fcts = inspect.getmembers(module, predicate)
    # convert handler
    partial_fcts = [socket_io_handler(app)(func_handler) for _, func_handler in member_fcts]
    app[APP_CLIENT_SOCKET_DECORATED_HANDLERS_KEY] = partial_fcts
    # register the fcts
    for func in partial_fcts:
        sio.on(func.__name__, handler=func)
