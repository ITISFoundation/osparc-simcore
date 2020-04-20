import logging
from typing import Dict, Optional, Tuple, Union

import attr
import sqlalchemy as sa
from aiohttp import web
from aiohttp_security.abc import AbstractAuthorizationPolicy
from aiopg.sa import Engine
from aiopg.sa.result import ResultProxy, RowProxy
from expiringdict import ExpiringDict
from tenacity import retry

from servicelib.aiopg_utils import PostgresRetryPolicyUponOperation
from servicelib.application_keys import APP_DB_ENGINE_KEY

from .db_models import UserStatus, users
from .security_access_model import RoleBasedAccessModel, check_access

log = logging.getLogger(__file__)


@attr.s(auto_attribs=True, frozen=True)
class AuthorizationPolicy(AbstractAuthorizationPolicy):
    app: web.Application
    access_model: RoleBasedAccessModel
    timed_cache: ExpiringDict = attr.ib(
        init=False, default=ExpiringDict(max_len=100, max_age_seconds=10)
    )

    @property
    def engine(self) -> Engine:
        """Lazy getter since the database is not available upon setup

        :return: database's engine
        """
        # TODO: what if db is not available?
        # return self.app.config_dict[APP_DB_ENGINE_KEY]
        return self.app[APP_DB_ENGINE_KEY]

    @retry(**PostgresRetryPolicyUponOperation(log).kwargs)
    async def _pg_query_user(self, identity: str) -> RowProxy:
        # NOTE: Keeps a cache for a few seconds. Observed successive streams of this query
        row = self.timed_cache.get(identity)
        if not row:
            query = users.select().where(
                sa.and_(users.c.email == identity, users.c.status != UserStatus.BANNED)
            )
            async with self.engine.acquire() as conn:
                # NOTE: sometimes it raises psycopg2.DatabaseError in #880 and #1160
                ret: ResultProxy = await conn.execute(query)
                row: RowProxy = await ret.fetchone()
            self.timed_cache[identity] = row
        return row

    async def authorized_userid(self, identity: str) -> Optional[str]:
        """ Retrieve authorized user id.

        Return the user_id of the user identified by the identity
        or "None" if no user exists related to the identity.
        """
        # TODO: why users.c.user_login_key!=users.c.email
        user = await self._pg_query_user(identity)
        return user.get('id'), user.get('email') if user else None

    async def permits(
        self,
        identity: str,
        permission: Union[str, Tuple],
        context: Optional[Dict] = None,
    ) -> bool:
        """ Determines whether an identified user has permission

        :param identity: session identified corresponds to the user's email as defined in login.handlers.registration
        :param permission: name of the operation that user wants to execute OR a tuple as (operator.and_|operator.or_, name1, name2, ...)
        :param context: context of the operation, defaults to None
        :return: True if user has permission to execute this operation within the given context
        """
        if identity is None or permission is None:
            log.debug(
                "Invalid indentity [%s] of permission [%s]. Denying access.",
                identity,
                permission,
            )
            return False

        user = await self._pg_query_user(identity)
        if user:
            role = user.get("role")
            return await check_access(self.access_model, role, permission, context)

        return False
