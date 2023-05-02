""" API for security subsystem.

"""
import logging

import passlib.hash
from aiohttp import web
from aiohttp_security.api import (
    AUTZ_KEY,
    authorized_userid,
    check_permission,
    forget,
    is_anonymous,
    remember,
)

from ._authorization import AuthorizationPolicy, RoleBasedAccessModel
from .security_roles import UserRole

log = logging.getLogger(__name__)


def encrypt_password(password: str) -> str:
    return passlib.hash.sha256_crypt.using(rounds=1000).hash(password)


def check_password(password: str, password_hash: str) -> bool:
    return passlib.hash.sha256_crypt.verify(password, password_hash)


def get_access_model(app: web.Application) -> RoleBasedAccessModel:
    autz_policy: AuthorizationPolicy = app[AUTZ_KEY]
    return autz_policy.access_model


def clean_auth_policy_cache(app: web.Application) -> None:
    autz_policy: AuthorizationPolicy = app[AUTZ_KEY]
    autz_policy.timed_cache.clear()


__all__: tuple[str, ...] = (
    "authorized_userid",
    "check_permission",
    "encrypt_password",
    "forget",
    "get_access_model",
    "is_anonymous",
    "remember",
    "UserRole",
)

# nopycln: file
