from functools import wraps

from aiohttp import web
from servicelib.aiohttp.typing_extension import Handler

from .security_api import check_permission


def permission_required(permissions: str):
    """Decorator that checks whether user permissions are fulfilled.
        The function will throw an exception in case of disallowance.

    :param handler: the function to check syntax must have web.Request as parameter
    If user is not authorized - raises HTTPUnauthorized,
    if user is authorized and does not have permission -
    raises HTTPForbidden.
    """

    def decorator(handler: Handler):
        @wraps(handler)
        async def wrapped(request: web.Request):
            await check_permission(request, permissions)
            ret = await handler(request)
            return ret

        return wrapped

    return decorator
