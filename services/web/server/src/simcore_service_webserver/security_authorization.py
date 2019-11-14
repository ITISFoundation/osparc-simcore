import logging
from typing import Dict, Optional, Tuple, Union

import attr
import psycopg2
import sqlalchemy as sa
from aiohttp import web
from aiohttp_security.abc import AbstractAuthorizationPolicy
from aiopg.sa import Engine
from tenacity import (RetryCallState, after_log, retry,
                      retry_if_exception_type, stop_after_attempt, wait_fixed)

from servicelib.application_keys import APP_DB_ENGINE_KEY

from .db_models import UserStatus, users
from .security_access_model import RoleBasedAccessModel, check_access

log = logging.getLogger(__file__)



def raise_http_unavailable_error(retry_state: RetryCallState):
    # TODO: mark incident on db to determine the quality of service. E.g. next time we do not stop.
    # TODO: add header with Retry-After
    #obj, query = retry_state.args
    #obj.app.register_incidents
    # https://tools.ietf.org/html/rfc7231#section-7.1.3
    raise web.HTTPServiceUnavailable()


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

    @retry(
        retry=retry_if_exception_type(psycopg2.DatabaseError),
        wait=wait_fixed(2),
        stop=stop_after_attempt(3),
        after=after_log(log, logging.ERROR),
        retry_error_callback=raise_http_unavailable_error)
    async def _safe_execute(self, query):
        # NOTE: psycopg2.DatabaseError in #880 and #1160
        # http://initd.org/psycopg/docs/module.html
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
        user = await self._safe_execute( users.select().where(
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

        user = await self._safe_execute( users.select().where(
            sa.and_(users.c.email == identity,
                    users.c.status != UserStatus.BANNED)
            )
        )
        if user:
            role = user.get('role')
            return await check_access(self.access_model, role, permission, context)

        return False
