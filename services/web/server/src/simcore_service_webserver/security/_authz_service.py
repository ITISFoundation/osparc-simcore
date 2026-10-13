# mypy: disable-error-code=truthy-function


import os
import re
from typing import Final

import aiohttp_security.api
import passlib.hash
from aiohttp import web
from cryptography.exceptions import InvalidKey
from cryptography.hazmat.primitives.kdf.argon2 import Argon2id

from ._authz_access_model import RoleBasedAccessModel
from ._authz_policy import AuthorizationPolicy
from ._constants import PERMISSION_PRODUCT_LOGIN_KEY

assert PERMISSION_PRODUCT_LOGIN_KEY  # nosec


def get_access_model(app: web.Application) -> RoleBasedAccessModel:
    autz_policy = app[aiohttp_security.api.AUTZ_KEY]
    assert isinstance(autz_policy, AuthorizationPolicy)  # nosec
    return autz_policy.access_model


async def clean_auth_policy_cache(app: web.Application) -> None:
    autz_policy = app[aiohttp_security.api.AUTZ_KEY]
    assert isinstance(autz_policy, AuthorizationPolicy)  # nosec
    await autz_policy.clear_cache()


#
# utils (i.e. independent from setup)
#


# OWASP minimum argon2id parameters; they are stored in each hash
_ARGON2_MEMORY_COST_KIB: Final = 19 * 1024
_ARGON2_ITERATIONS: Final = 2
_ARGON2_LANES: Final = 1
_ARGON2_PHC_PARAMS: Final = re.compile(r"^\$argon2id\$v=19\$m=(\d+),t=(\d+),p=(\d+)\$")


def encrypt_password(password: str) -> str:
    # keeps passlib's TypeError (.encode() would raise AttributeError instead)
    if not isinstance(password, str):
        msg = f"password must be str, got {type(password).__name__}"
        raise TypeError(msg)
    kdf = Argon2id(
        salt=os.urandom(16),
        length=32,
        iterations=_ARGON2_ITERATIONS,
        lanes=_ARGON2_LANES,
        memory_cost=_ARGON2_MEMORY_COST_KIB,
    )
    return kdf.derive_phc_encoded(password.encode())


def check_password(password: str, password_hash: str) -> bool:
    if password_hash.startswith("$argon2"):
        try:
            Argon2id.verify_phc_encoded(password.encode(), password_hash)
        except InvalidKey:
            return False
        return True

    # legacy hashes
    is_valid: bool = passlib.hash.sha256_crypt.verify(password, password_hash)
    return is_valid


def password_needs_rehash(password_hash: str) -> bool:
    match = _ARGON2_PHC_PARAMS.match(password_hash)
    if match is None:
        return True
    memory_cost, iterations, lanes = (int(g) for g in match.groups())
    return (memory_cost, iterations, lanes) != (_ARGON2_MEMORY_COST_KIB, _ARGON2_ITERATIONS, _ARGON2_LANES)
