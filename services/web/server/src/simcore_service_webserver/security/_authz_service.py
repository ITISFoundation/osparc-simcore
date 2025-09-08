# mypy: disable-error-code=truthy-function


import aiohttp_security.api  # type: ignore[import-untyped]
import passlib.hash
from aiohttp import web
from models_library.users import UserID
from simcore_service_webserver.products._models import Product

from ..db.plugin import get_asyncpg_engine
from . import _authz_repository
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


async def is_user_in_product_support_group(
    app: web.Application, *, product: Product, user_id: UserID
) -> bool:
    """Checks if the user belongs to the support group of the given product.
    If the product does not have a support group, returns False.
    """
    if product.support_standard_group_id is None:
        return False
    return await _authz_repository.is_user_in_group(
        get_asyncpg_engine(app),
        user_id=user_id,
        group_id=product.support_standard_group_id,
    )


#
# utils (i.e. independent from setup)
#


def encrypt_password(password: str) -> str:
    hashed: str = passlib.hash.sha256_crypt.using(rounds=1000).hash(password)
    return hashed


def check_password(password: str, password_hash: str) -> bool:
    is_valid: bool = passlib.hash.sha256_crypt.verify(password, password_hash)
    return is_valid
