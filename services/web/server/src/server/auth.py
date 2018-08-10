""" User's authentication and authorization

    - authentication: Identity gets ide

    - based in aiohttp_security library : https://aiohttp-security.readthedocs.io/en/latest/

"""
# pylint: disable=assignment-from-no-return
import logging
import sqlalchemy as sa

from aiohttp_security import (
    setup as setup_security,
    SessionIdentityPolicy
)
from aiohttp_security.abc import AbstractAuthorizationPolicy
from passlib.hash import sha256_crypt


from .db import model

_LOGGER = logging.getLogger(__file__)


class DBAuthorizationPolicy(AbstractAuthorizationPolicy):
    def __init__(self, app, db_engine_key):
        # Lazy getter
        self._app = app
        self._dbkey = db_engine_key

    @property
    def dbengine(self):
        return self._app[self._dbkey]

    async def authorized_userid(self, identity):
        """Retrieve authorized user id.

        Return the user_id of the user identified by the identity
        or "None" if no user exists related to the identity.
        """
        # pylint: disable=E1120
        async with self.dbengine.acquire() as conn:
            where = sa.and_(model.users.c.login == identity,
                            sa.not_(model.users.c.disabled))
            query = model.users.count().where(where)
            ret = await conn.scalar(query)
            if ret:
                return identity
            return None

    async def permits(self, identity, permission, context=None):
        """Check user model.permissions.

        Return True if the identity is allowed the permission in the
        current context, else return False.
        """
        _LOGGER.debug("context: %s", context)
        if identity is None:
            return False

        async with self.dbengine.acquire() as conn:
            where = sa.and_(model.users.c.login == identity,
                            sa.not_(model.users.c.disabled))
            query = model.users.select().where(where)
            ret = await conn.execute(query)
            user = await ret.fetchone()
            if user is not None:
                user_id = user[0]
                is_superuser = user[3]
                if is_superuser:
                    return True

                where = model.permissions.c.user_id == user_id
                query = model.permissions.select().where(where)
                ret = await conn.execute(query)
                result = await ret.fetchall()
                if ret is not None:
                    for record in result:
                        if record.perm_name == permission:
                            return True

            return False


async def check_credentials(db_engine, username, password):
    async with db_engine.acquire() as conn:
        where = sa.and_(model.users.c.login == username,
                        sa.not_(model.users.c.disabled))
        query = model.users.select().where(where)
        ret = await conn.execute(query)
        user = await ret.fetchone()
        if user is not None:
            _hash = user[2]  # password
            return sha256_crypt.verify(password, _hash)
    return False


generate_password_hash = sha256_crypt.hash


def setup_auth(app):
    _LOGGER.debug("Setting up %s ...", __name__)

    # WARNING: expected aiosession already initialized!
    identity_policy = SessionIdentityPolicy()

    # FIXME: cannot guarantee correct config key for db"s engine!
    authorization_policy = DBAuthorizationPolicy(app, "db_engine")
    setup_security(app, identity_policy, authorization_policy)
