import logging
from dataclasses import dataclass, field
from typing import TypedDict

import sqlalchemy as sa
from aiohttp import web
from aiohttp_security.abc import AbstractAuthorizationPolicy
from aiopg.sa import Engine
from aiopg.sa.result import ResultProxy
from expiringdict import ExpiringDict
from models_library.basic_types import IdInt
from servicelib.aiohttp.aiopg_utils import PostgresRetryPolicyUponOperation
from simcore_postgres_database.models.users import UserRole
from tenacity import retry

from ..db.models import UserStatus, users
from ..db.plugin import get_database_engine
from ._access_model import ContextType, RoleBasedAccessModel, check_access

_logger = logging.getLogger(__name__)


class _UserIdentity(TypedDict, total=True):
    id: IdInt
    role: UserRole


def _create_expiring_dict():
    return ExpiringDict(max_len=100, max_age_seconds=10)


@dataclass(frozen=True)
class AuthorizationPolicy(AbstractAuthorizationPolicy):
    app: web.Application
    access_model: RoleBasedAccessModel
    timed_cache: ExpiringDict = field(default_factory=_create_expiring_dict)

    @property
    def engine(self) -> Engine:
        """Lazy getter since the database is not available upon setup"""
        _engine: Engine = get_database_engine(self.app)
        return _engine

    @retry(**PostgresRetryPolicyUponOperation(_logger).kwargs)
    async def _get_active_user_with(self, identity: str) -> _UserIdentity | None:
        # NOTE: Keeps a cache for a few seconds. Observed successive streams of this query
        user: _UserIdentity | None = self.timed_cache.get(identity, None)
        if user is None:
            async with self.engine.acquire() as conn:
                # NOTE: sometimes it raises psycopg2.DatabaseError in #880 and #1160
                result: ResultProxy = await conn.execute(
                    sa.select(users.c.id, users.c.role).where(
                        (users.c.email == identity)
                        & (users.c.status == UserStatus.ACTIVE)
                    )
                )
                row = await result.fetchone()
            if row is not None:
                assert row["id"]  # nosec
                assert row["role"]  # nosec
                self.timed_cache[identity] = user = _UserIdentity(
                    id=row.id, role=row.role
                )

        return user

    async def authorized_userid(self, identity: str) -> int | None:
        """Retrieve authorized user id.

        Return the user_id of the user identified by the identity
        or "None" if no user exists related to the identity.
        """
        user: _UserIdentity | None = await self._get_active_user_with(identity)

        if user is None:
            return None

        user_id: int = user["id"]
        return user_id

    async def permits(
        self,
        identity: str,
        permission: str,
        context: ContextType = None,
    ) -> bool:
        """Determines whether an identified user has permission

        :param identity: session identified corresponds to the user's email as defined in login.handlers_registration
        :param permission: name of the operation that user wants to execute OR a tuple as (operator.and_|operator.or_, name1, name2, ...)
        :param context: context of the operation, defaults to None
        :return: True if user has permission to execute this operation within the given context
        """
        if identity is None or permission is None:
            _logger.debug(
                "Invalid %s of %s. Denying access.",
                f"{identity=}",
                f"{permission=}",
            )
            return False

        user = await self._get_active_user_with(identity)
        if user is None:
            return False

        role = user.get("role")
        return await check_access(self.access_model, role, permission, context)
