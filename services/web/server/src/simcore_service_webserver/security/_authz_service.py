# mypy: disable-error-code=truthy-function


import aiohttp_security.api  # type: ignore[import-untyped]
import passlib.hash
from aiohttp import web

from ._authz_access_model import RoleBasedAccessModel
from ._authz_policy import AuthorizationPolicy
from ._constants import PERMISSION_PRODUCT_LOGIN_KEY

assert PERMISSION_PRODUCT_LOGIN_KEY  # nosec


def get_access_model(app: web.Application) -> RoleBasedAccessModel:
    autz_policy: AuthorizationPolicy = app[aiohttp_security.api.AUTZ_KEY]
    return autz_policy.access_model


async def clean_auth_policy_cache(app: web.Application) -> None:
    autz_policy: AuthorizationPolicy = app[aiohttp_security.api.AUTZ_KEY]
    await autz_policy.clear_cache()


#
# utils (i.e. independent from setup)
#


def encrypt_password(password: str) -> str:
    hashed: str = passlib.hash.sha256_crypt.using(rounds=1000).hash(password)
    return hashed


def check_password(password: str, password_hash: str) -> bool:
    is_valid: bool = passlib.hash.sha256_crypt.verify(password, password_hash)
    return is_valid
