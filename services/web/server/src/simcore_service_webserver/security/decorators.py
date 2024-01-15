from functools import wraps

from aiohttp import web
from servicelib.aiohttp.typing_extension import Handler

from ..products.api import get_product_name
from .api import check_permission


def permission_required(permissions: str):
    """Decorator that checks whether user permissions are fulfilled.
        The function will throw an exception in case of disallowance.

    :param handler: the function to check syntax must have web.Request as parameter
    If user is not authorized - raises HTTPUnauthorized,
    if user is authorized and does not have permission -
    raises HTTPForbidden.
    """

    def _decorator(handler: Handler):
        @wraps(handler)
        async def _wrapped(request: web.Request):

            # FIXME: avoid using check_permissions in the api!
            await check_permission(
                request,
                permissions,
                context={"product_name": get_product_name(request)},
            )
            return await handler(request)

        return _wrapped

    return _decorator
