# mypy: disable-error-code=truthy-function


import aiohttp_security.api  # type: ignore[import-untyped]
from aiohttp import web
from models_library.users import UserID

from ._authz_access_model import AuthContextDict, OptionalContext
from ._constants import PERMISSION_PRODUCT_LOGIN_KEY

assert PERMISSION_PRODUCT_LOGIN_KEY  # nosec


async def is_anonymous(request: web.Request) -> bool:
    """
    User is considered anonymous if there is not verified identity in request.
    """
    is_user_id_none: bool = await aiohttp_security.api.is_anonymous(request)
    return is_user_id_none


async def check_user_authorized(request: web.Request) -> UserID:
    """
    Raises:
        web.HTTPUnauthorized: for anonymous user (i.e. user_id is None)

    """
    # NOTE: Same as aiohttp_security.api.check_authorized
    user_id: UserID | None = await aiohttp_security.api.authorized_userid(request)
    if user_id is None:
        raise web.HTTPUnauthorized
    return user_id


async def check_user_permission(
    request: web.Request, permission: str, *, context: OptionalContext = None
) -> None:
    """Checker that passes only to authoraised users with given permission.

    Raises:
        web.HTTPUnauthorized: If user is not authorized
        web.HTTPForbidden: If user is authorized and does not have permission
    """
    # NOTE: Same as aiohttp_security.api.check_permission
    context = context or AuthContextDict()
    if not context.get("authorized_uid"):
        context["authorized_uid"] = await check_user_authorized(request)

    allowed = await aiohttp_security.api.permits(request, permission, context)
    if not allowed:
        msg = "You do not have sufficient access rights for"
        if permission == PERMISSION_PRODUCT_LOGIN_KEY:
            msg += f" {context.get('product_name')}"
        else:
            msg += f" {permission}"
        raise web.HTTPForbidden(text=msg)
