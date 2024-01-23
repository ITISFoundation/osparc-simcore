""" API for security subsystem.

"""

import aiohttp_security.api
import passlib.hash
from aiohttp import web
from models_library.users import UserID

from ._authz_access_model import OptionalContext, RoleBasedAccessModel
from ._authz_policy import AuthorizationPolicy
from ._identity_api import forget_identity, remember_identity


def get_access_model(app: web.Application) -> RoleBasedAccessModel:
    autz_policy: AuthorizationPolicy = app[aiohttp_security.api.AUTZ_KEY]
    return autz_policy.access_model


async def clean_auth_policy_cache(app: web.Application) -> None:
    autz_policy: AuthorizationPolicy = app[aiohttp_security.api.AUTZ_KEY]
    await autz_policy.clear_cache()


async def check_permission(
    request: web.Request, permission: str, *, context: OptionalContext = None
) -> None:
    """Checker that passes only to authoraised users with given permission.

    Raises:
        web.HTTPUnauthorized: If user is not authorized
        web.HTTPForbidden: If user is authorized and does not have permission
    """
    await aiohttp_security.api.check_permission(request, permission, context)


async def authorized_userid(request: web.Request) -> UserID | None:
    return await aiohttp_security.api.authorized_userid(request)


async def is_anonymous(request: web.Request) -> bool:
    """
    User is considered anonymous if there is not identityin request.
    """
    is_user_id_none: bool = await aiohttp_security.api.is_anonymous(request)
    return is_user_id_none


async def get_user_id_or_raise_if_unauthorized(request: web.Request) -> UserID:
    """
    Raises:
        web.HTTPUnauthorized: for anonymous user (i.e. user_id is None)

    """
    userid = await aiohttp_security.api.authorized_userid(request)

    # FIXME: verify correct product or rather interect get_product_name?
    # current_product_name = get_product_name(request)
    # authorized_product_name =
    # TODO: perhaps we can store the product in a session as well

    if userid is None:
        raise web.HTTPUnauthorized
    return userid


#
# utils (i.e. independent from setup)
#


def encrypt_password(password: str) -> str:
    hashed: str = passlib.hash.sha256_crypt.using(rounds=1000).hash(password)
    return hashed


def check_password(password: str, password_hash: str) -> bool:
    is_valid: bool = passlib.hash.sha256_crypt.verify(password, password_hash)
    return is_valid


assert forget_identity  # nosec
assert remember_identity  # nosec


__all__: tuple[str, ...] = (
    "authorized_userid",
    "check_permission",
    "encrypt_password",
    "forget_identity",
    "get_access_model",
    "is_anonymous",
    "remember_identity",
)
