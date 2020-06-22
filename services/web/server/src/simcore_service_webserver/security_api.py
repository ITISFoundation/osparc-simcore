""" API for security subsystem.

"""
# pylint: disable=assignment-from-no-return
import logging

import passlib.hash
import sqlalchemy as sa
from aiohttp import web
from aiohttp_security.api import (
    AUTZ_KEY,
    authorized_userid,
    check_permission,
    forget,
    is_anonymous,
    remember,
)
from aiopg.sa import Engine

from .db_models import UserStatus, users
from .security_authorization import AuthorizationPolicy, RoleBasedAccessModel
from .security_roles import UserRole

log = logging.getLogger(__file__)


async def check_credentials(engine: Engine, email: str, password: str) -> bool:
    async with engine.acquire() as conn:
        query = users.select().where(
            sa.and_(users.c.email == email, users.c.status != UserStatus.BANNED)
        )
        ret = await conn.execute(query)
        user = await ret.fetchone()
        if user is not None:
            return check_password(password, user["password_hash"])
    return False


def encrypt_password(password: str) -> str:
    return passlib.hash.sha256_crypt.encrypt(password, rounds=1000)


def check_password(password: str, password_hash: str) -> bool:
    return passlib.hash.sha256_crypt.verify(password, password_hash)


def get_access_model(app: web.Application) -> RoleBasedAccessModel:
    autz_policy: AuthorizationPolicy = app[AUTZ_KEY]
    return autz_policy.access_model


def clean_auth_policy_cache(app: web.Application) -> None:
    autz_policy: AuthorizationPolicy = app[AUTZ_KEY]
    autz_policy.timed_cache.clear()


__all__ = (
    "encrypt_password",
    "check_credentials",
    "authorized_userid",
    "forget",
    "remember",
    "is_anonymous",
    "check_permission",
    "get_access_model",
    "UserRole",
)
