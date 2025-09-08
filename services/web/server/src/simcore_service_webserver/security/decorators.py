from contextlib import suppress
from functools import wraps

import aiohttp_security.api  # type: ignore[import-untyped]
from aiohttp import web
from servicelib.aiohttp.typing_extension import Handler

from ..products.products_web import get_current_product
from ._authz_access_model import AuthContextDict
from ._authz_access_roles import GROUP_PERMISSIONS
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
            context = AuthContextDict()
            context["authorized_uid"] = await check_user_authorized(request)

            # Check role-based permissions first
            role_allowed = await aiohttp_security.api.permits(
                request, permission, context
            )
            if role_allowed:
                return await handler(request)

            # Check group-based permissions
            with suppress(
                Exception
                # If product or group check fails, continue to deny access
                # NOTE: Logging omitted to avoid exposing internal errors
            ):

                product = get_current_product(request)

                if product.support_standard_group_id is not None:
                    # FIXME: Group membership API will be implemented later
                    # For now, always returns False
                    is_member = False  # Placeholder

                    if is_member:
                        group_permissions = GROUP_PERMISSIONS.get("support_group", [])
                        if permission in group_permissions:
                            return await handler(request)

            # Neither role nor group permissions granted
            msg = f"You do not have sufficient access rights for {permission}"
            raise web.HTTPForbidden(text=msg)

        return _wrapped

    return _decorator
