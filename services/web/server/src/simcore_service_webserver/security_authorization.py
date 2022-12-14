import logging
from typing import Optional, TypedDict, Union

import attr
import sqlalchemy as sa
from aiohttp import web
from aiohttp_security.abc import AbstractAuthorizationPolicy
from aiopg.sa import Engine
from aiopg.sa.result import ResultProxy
from expiringdict import ExpiringDict
from models_library.basic_types import IdInt
from servicelib.aiohttp.aiopg_utils import PostgresRetryPolicyUponOperation
from servicelib.aiohttp.application_keys import APP_DB_ENGINE_KEY
from simcore_postgres_database.models.users import UserRole
from tenacity import retry

from .db_models import UserStatus, users
from .security_access_model import RoleBasedAccessModel, check_access

log = logging.getLogger(__name__)


class _UserIdentity(TypedDict, total=True):
    id: IdInt
    role: UserRole


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
    async def _get_active_user_with(self, identity: str) -> Optional[_UserIdentity]:
        # NOTE: Keeps a cache for a few seconds. Observed successive streams of this query
        user: Optional[_UserIdentity] = self.timed_cache.get(identity)
        if user is None:
            async with self.engine.acquire() as conn:
                # NOTE: sometimes it raises psycopg2.DatabaseError in #880 and #1160
                result: ResultProxy = await conn.execute(
                    sa.select([users.c.id, users.c.role]).where(
                        (users.c.email == identity)
                        & (users.c.status == UserStatus.ACTIVE)
                    )
                )
                row = await result.fetchone()
            if row is not None:
                assert row["id"]  # nosec
                assert row["role"]  # nosec
                self.timed_cache[identity] = user = dict(row.items())

        return user

    async def authorized_userid(self, identity: str) -> Optional[int]:
        """Retrieve authorized user id.

        Return the user_id of the user identified by the identity
        or "None" if no user exists related to the identity.
        """
        # TODO: why users.c.user_login_key!=users.c.email
        user: Optional[_UserIdentity] = await self._get_active_user_with(identity)
        return user["id"] if user else None

    async def permits(
        self,
        identity: str,
        permission: Union[str, tuple],
        context: Optional[dict] = None,
    ) -> bool:
        """Determines whether an identified user has permission

        :param identity: session identified corresponds to the user's email as defined in login.handlers_registration
        :param permission: name of the operation that user wants to execute OR a tuple as (operator.and_|operator.or_, name1, name2, ...)
        :param context: context of the operation, defaults to None
        :return: True if user has permission to execute this operation within the given context
        """
        if identity is None or permission is None:
            log.debug(
                "Invalid %s of %s. Denying access.",
                f"{identity=}",
                f"{permission=}",
            )
            return False

        user = await self._get_active_user_with(identity)
        if user:
            role = user.get("role")
            return await check_access(self.access_model, role, permission, context)

        return False
