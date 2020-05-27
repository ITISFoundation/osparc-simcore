from functools import wraps
from typing import Coroutine

from aiohttp import web

from .security_api import check_permission


def permission_required(permissions: str):
    """Decorator that checks whether user permissions are fulfilled.
        The function will throw an exception in case of disallowance.

    :param handler: the function to check syntax must have web.Request as parameter
    """

    def decorator(handler: Coroutine):
        @wraps(handler)
        async def wrapped(request: web.Request):
            await check_permission(request, permissions)
            ret = await handler(request)
            return ret

        return wrapped

    return decorator
