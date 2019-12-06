import logging
from typing import Dict, Optional, Tuple, Union

import attr
import sqlalchemy as sa
from aiohttp import web
from tenacity import retry

from aiohttp_security.abc import AbstractAuthorizationPolicy
from aiopg.sa import Engine
from servicelib.aiopg_utils import postgres_service_retry_policy_kwargs
from servicelib.application_keys import APP_DB_ENGINE_KEY

from .db_models import UserStatus, users
from .security_access_model import RoleBasedAccessModel, check_access

log = logging.getLogger(__file__)


@attr.s(auto_attribs=True, frozen=True)
class AuthorizationPolicy(AbstractAuthorizationPolicy):
    app: web.Application
    access_model: RoleBasedAccessModel

    @property
    def engine(self) -> Engine:
        """Lazy getter since the database is not available upon setup

        :return: database's engine
        """
         # TODO: what if db is not available?
        #return self.app.config_dict[APP_DB_ENGINE_KEY]
        return self.app[APP_DB_ENGINE_KEY]

    @retry(**postgres_service_retry_policy_kwargs)
    async def _exec_pg_query(self, query):
        # NOTE: psycopg2.DatabaseError in #880 and #1160
        async with self.engine.acquire() as conn:
            ret = await conn.execute(query)
            res = await ret.fetchone()
        return res

    async def authorized_userid(self, identity: str) -> Optional[str]:
        """ Retrieve authorized user id.

        Return the user_id of the user identified by the identity
        or "None" if no user exists related to the identity.
        """
        # TODO: why users.c.user_login_key!=users.c.email
        user = await self._exec_pg_query( users.select().where(
            sa.and_(users.c.email == identity,
                    users.c.status != UserStatus.BANNED)
        ))
        return user["id"] if user else None

    async def permits(self, identity: str, permission: Union[str,Tuple], context: Optional[Dict]=None) -> bool:
        """ Determines whether an identified user has permission

        :param identity: session identified corresponds to the user's email as defined in login.handlers.registration
        :param permission: name of the operation that user wants to execute OR a tuple as (operator.and_|operator.or_, name1, name2, ...)
        :param context: context of the operation, defaults to None
        :return: True if user has permission to execute this operation within the given context
        """
        if identity is None or permission is None:
            log.debug("Invalid indentity [%s] of permission [%s]. Denying access.", identity, permission)
            return False

        user = await self._exec_pg_query( users.select().where(
            sa.and_(users.c.email == identity,
                    users.c.status != UserStatus.BANNED)
            )
        )
        if user:
            role = user.get('role')
            return await check_access(self.access_model, role, permission, context)

        return False
