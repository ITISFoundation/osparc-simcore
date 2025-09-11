from functools import wraps

from aiohttp import web
from servicelib.aiohttp.typing_extension import Handler

from ._authz_web import check_user_permission_with_groups
from .security_web import check_user_permission


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
            await check_user_permission(request, permissions)

            return await handler(request)

        return _wrapped

    return _decorator


def group_or_role_permission_required(permission: str):
    """Decorator that checks user permissions via role or gorup membership

    User gets access if they have permission via role OR group membership.

    If user is not authorized - raises HTTPUnauthorized,
    if user is authorized but lacks both role and group permissions - raises HTTPForbidden.
    """

    def _decorator(handler: Handler):
        @wraps(handler)
        async def _wrapped(request: web.Request):
            await check_user_permission_with_groups(request, permission)

            return await handler(request)

        return _wrapped

    return _decorator
