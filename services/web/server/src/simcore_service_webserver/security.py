""" Security subsystem.

    - Responsible of authentication and authorization


    See login/decorators.py
    Based on https://aiohttp-security.readthedocs.io/en/latest/
"""
# pylint: disable=assignment-from-no-return
import logging

import aiohttp_security
import passlib.hash
import sqlalchemy as sa
from aiohttp_security.api import (authorized_userid, check_permission, forget,
                                  is_anonymous, remember)
from aiohttp_security.session_identity import SessionIdentityPolicy
from aiopg.sa import Engine

from .db_models import UserStatus, users
from .security_access_model import RoleBasedAccessModel
from .security_authorization import AuthorizationPolicy
from .security_roles import ROLES_PERMISSIONS

log = logging.getLogger(__file__)

# aliases
forget = forget
remember = remember
is_anonymous = is_anonymous
authorized_userid = authorized_userid
check_permission = check_permission


async def check_credentials(engine: Engine, email: str, password: str) -> bool:
    async with engine.acquire() as conn:
        query = users.select().where(
            sa.and_(users.c.email == email,
            users.c.status != UserStatus.BANNED)
        )
        ret = await conn.execute(query)
        user = await ret.fetchone()
        if user is not None:
            return check_password(password, user['password_hash'] )
    return False

def encrypt_password(password):
    return passlib.hash.sha256_crypt.encrypt(password, rounds=1000)

def check_password(password, password_hash):
    return passlib.hash.sha256_crypt.verify(password, password_hash)

def setup(app):
    log.debug("Setting up %s ...", __name__)

    # Once user is identified, an identity string is created for that user
    identity_policy = SessionIdentityPolicy()

    # TODO: limitations is that it cannot contain checks need to be added here
    access_model = RoleBasedAccessModel.from_rawdata(ROLES_PERMISSIONS)

    # TODO: create basic/bearer authentication policy based on tokens instead of cookies!!
    authorization_policy = AuthorizationPolicy(app, access_model)
    aiohttp_security.setup(app, identity_policy, authorization_policy)

setup_security = setup
generate_password_hash = encrypt_password

__all__ = (
    'setup_security',
    'generate_password_hash', 'check_credentials',
    'authorized_userid', 'forget', 'remember', 'is_anonymous', 'check_permission'
)
