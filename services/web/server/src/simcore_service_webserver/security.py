""" Security subsystem.

    - Responsible of authentication and authorization

    Based on https://aiohttp-security.readthedocs.io/en/latest/
"""
# pylint: disable=assignment-from-no-return
# pylint: disable=unused-import
import logging

import aiohttp_security
import passlib.hash
import sqlalchemy as sa
from aiohttp import web
from aiohttp_security.abc import AbstractAuthorizationPolicy
from aiohttp_security.api import (authorized_userid, forget, has_permission,
                                  is_anonymous, login_required, remember)
from aiohttp_security.session_identity import SessionIdentityPolicy
from aiopg.sa import Engine

from .application_keys import APP_DB_ENGINE_KEY
from .db_models import UserRole, UserStatus, users
from .session import setup_session

log = logging.getLogger(__file__)


class DBAuthorizationPolicy(AbstractAuthorizationPolicy):
    def __init__(self, app: web.Application):
        self._app = app

    @property
    def engine(self) -> Engine:
         # Lazy getter since db is not available upon construction

         # TODO: what if db is not available?
        return self._app[APP_DB_ENGINE_KEY]

    async def authorized_userid(self, identity: str):
        """ Retrieve authorized user id.

        Return the user_id of the user identified by the identity
        or "None" if no user exists related to the identity.
        """
        # pylint: disable=E1120
        async with self.engine.acquire() as conn:
            # TODO: why users.c.user_login_key!=users.c.email
            query = users.select().where(
                    sa.and_(users.c.email == identity,
                            users.c.status != UserStatus.BANNED)
            )
            ret = await conn.execute(query)
            user = await ret.fetchone()
            return user["id"] if user else None

    async def permits(self, identity: str, permission: UserRole, context=None):
        """ Check user's permissions

        Return True if the identity is allowed the permission in the
        current context, else return False.
        """
        log.debug("context: %s", context)

        if identity is None or permission is None:
            return False

        async with self.engine.acquire() as conn:
            query = users.select().where(
                sa.and_(users.c.email == identity,
                users.c.status != UserStatus.BANNED)
            )
            ret = await conn.execute(query)
            user = await ret.fetchone()
            if user is not None:
                return permission <= user['role']
        return False

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
    # TODO: create basic/bearer authentication policy based on tokens instead of cookies!!

    authorization_policy = DBAuthorizationPolicy(app)
    aiohttp_security.setup(app, identity_policy, authorization_policy)

# aliases
generate_password_hash = encrypt_password
setup_security = setup

__all__ = (
    'setup_security',
    'generate_password_hash', 'check_credentials',
    'authorized_userid', 'forget', 'remember', 'is_anonymous',
    'login_required', 'has_permission' # decorators
)
