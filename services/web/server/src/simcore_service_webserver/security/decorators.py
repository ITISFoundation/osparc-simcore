from functools import wraps

import aiohttp_security.api  # type: ignore[import-untyped]
from aiohttp import web
from servicelib.aiohttp.typing_extension import Handler
from simcore_service_webserver.products import products_web

from ._authz_web import check_user_authorized
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
    """Decorator that checks user permissions via both roles AND groups (OR logic).

    User gets access if they have permission via role OR group membership.

    If user is not authorized - raises HTTPUnauthorized,
    if user is authorized but lacks both role and group permissions - raises HTTPForbidden.
    """

    def _decorator(handler: Handler):
        @wraps(handler)
        async def _wrapped(request: web.Request):
            context = {
                "authorized_uid": await check_user_authorized(request),
                "product_support_group_id": products_web.get_current_product(
                    request
                ).support_standard_group_id,
            }

            # Check both role-based and group-based permissions
            if await aiohttp_security.api.permits(request, permission, context):
                return await handler(request)

            # Neither role nor group permissions granted
            msg = f"You do not have sufficient access rights for {permission}"
            raise web.HTTPForbidden(text=msg)

        return _wrapped

    return _decorator
