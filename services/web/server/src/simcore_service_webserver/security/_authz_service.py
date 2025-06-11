# mypy: disable-error-code=truthy-function


import aiohttp_security.api  # type: ignore[import-untyped]
import passlib.hash
from aiohttp import web
from models_library.users import UserID

from ._authz_access_model import AuthContextDict, OptionalContext, RoleBasedAccessModel
from ._authz_policy import AuthorizationPolicy
from ._constants import PERMISSION_PRODUCT_LOGIN_KEY

assert PERMISSION_PRODUCT_LOGIN_KEY  # nosec


def get_access_model(app: web.Application) -> RoleBasedAccessModel:
    autz_policy: AuthorizationPolicy = app[aiohttp_security.api.AUTZ_KEY]
    return autz_policy.access_model


async def clean_auth_policy_cache(app: web.Application) -> None:
    autz_policy: AuthorizationPolicy = app[aiohttp_security.api.AUTZ_KEY]
    await autz_policy.clear_cache()


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
        raise web.HTTPForbidden(reason=msg)


#
# utils (i.e. independent from setup)
#


def encrypt_password(password: str) -> str:
    hashed: str = passlib.hash.sha256_crypt.using(rounds=1000).hash(password)
    return hashed


def check_password(password: str, password_hash: str) -> bool:
    is_valid: bool = passlib.hash.sha256_crypt.verify(password, password_hash)
    return is_valid
