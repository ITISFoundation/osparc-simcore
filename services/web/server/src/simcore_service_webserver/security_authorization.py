import logging
from typing import Dict, Tuple, Union

import attr
import sqlalchemy as sa
from aiohttp import web
from aiohttp_security.abc import AbstractAuthorizationPolicy
from aiopg.sa import Engine

from servicelib.application_keys import APP_DB_ENGINE_KEY

from .db_models import UserStatus, users
from .security_access_model import RoleBasedAccessModel

log = logging.getLogger(__file__)


@attr.s(auto_attribs=True, frozen=True)
class AuthorizationPolicy(AbstractAuthorizationPolicy):
    app: web.Application
    access_model: RoleBasedAccessModel

    @property
    def engine(self) -> Engine:
        """Lazy getter since the database is not available upon setup

        :return: database's engine
        :rtype: Engine
        """
         # TODO: what if db is not available?
        #return self.app.config_dict[APP_DB_ENGINE_KEY]
        return self.app[APP_DB_ENGINE_KEY]


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

    async def permits(self, identity: str, permission: Union[str,Tuple], context: Dict=None):
        """ Determines whether an identified user has permission

        :param identity: session identified corresponds to the user's email as defined in login.handlers.registration
        :type identity: str
        :param permission: name of the operation that user wants to execute OR a tuple as (operator.and_|operator.or_, name1, name2, ...)
        :type permission: str or tuple
        :param context: context of the operation, defaults to None
        :type context: Dict, optional
        :return: True if user has permission to execute this operation within the given context
        :rtype: bool
        """
        if identity is None or permission is None:
            log.debug("Invalid indentity [%s] of permission [%s]. Denying access.", identity, permission)
            return False

        async with self.engine.acquire() as conn:
            query = users.select().where(
                sa.and_(users.c.email == identity,
                        users.c.status != UserStatus.BANNED)
            )
            ret = await conn.execute(query)
            user = await ret.fetchone()

            if user:
                role = user.get('role')

                async def _check_expression(permission: Union[str, Tuple]):
                    if isinstance(permission, Tuple):
                        op, lhs, rhs = permission
                        return op(await _check_expression(lhs), await _check_expression(rhs))
                    return await self.access_model.can(role, permission, context)

                return await _check_expression(permission)

        return False
