# mypy: disable-error-code=truthy-function
"""

NOTE: DO NOT USE aiohttp_security.api directly but use this interface instead
"""

from ._authz_access_model import AuthContextDict
from ._authz_service import (
    check_password,
    check_user_authorized,
    check_user_permission,
    clean_auth_policy_cache,
    encrypt_password,
    get_access_model,
    is_anonymous,
)
from ._constants import PERMISSION_PRODUCT_LOGIN_KEY
from ._identity_web import forget_identity, remember_identity

__all__: tuple[str, ...] = (
    "PERMISSION_PRODUCT_LOGIN_KEY",
    "AuthContextDict",
    "check_password",
    "check_user_authorized",
    "check_user_permission",
    "clean_auth_policy_cache",
    "encrypt_password",
    "forget_identity",
    "get_access_model",
    "is_anonymous",
    "remember_identity",
)

# nopycln: file
