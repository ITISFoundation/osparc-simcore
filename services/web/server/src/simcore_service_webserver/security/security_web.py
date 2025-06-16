# mypy: disable-error-code=truthy-function
"""aiohttp.web-related interfaces i.e. web.Request is used in the inputs

NOTE: DO NOT USE aiohttp_security.api directly but use this interface instead
NOTE: functions in this module
"""

from ._authz_access_model import AuthContextDict
from ._authz_web import (
    check_user_authorized,
    check_user_permission,
    is_anonymous,
)
from ._constants import PERMISSION_PRODUCT_LOGIN_KEY
from ._identity_web import forget_identity, remember_identity

__all__: tuple[str, ...] = (
    "PERMISSION_PRODUCT_LOGIN_KEY",
    "AuthContextDict",
    "check_user_authorized",
    "check_user_permission",
    "forget_identity",
    "is_anonymous",
    "remember_identity",
)

# nopycln: file
