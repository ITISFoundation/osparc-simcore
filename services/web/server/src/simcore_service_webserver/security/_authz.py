""" AUTHoriZation (auth) policy:
"""
import logging
from typing import Final

from aiocache import cached
from aiocache.base import BaseCache
from aiohttp import web
from aiohttp_security.abc import AbstractAuthorizationPolicy
from simcore_postgres_database.errors import DatabaseError

from ..db.plugin import get_database_engine
from ._authz_access_model import OptionalContext, RoleBasedAccessModel, check_access
from ._authz_db import AuthInfoDict, get_active_user_or_none
from ._identity import IdentityStr

_logger = logging.getLogger(__name__)

_SECOND = 1  # in seconds
_ACTIVE_USER_AUTHZ_CACHE_TTL: Final = 10 * _SECOND


class AuthorizationPolicy(AbstractAuthorizationPolicy):
    def __init__(self, app: web.Application, access_model: RoleBasedAccessModel):
        self._app = app
        self._access_model = access_model

    @cached(
        ttl=_ACTIVE_USER_AUTHZ_CACHE_TTL,
        namespace=__name__,
        key_builder=lambda f, self, email: f"{f.__name__}/{email}",
        noself=True,
    )
    async def _get_auth_or_none(self, email: IdentityStr) -> AuthInfoDict | None:
        """Keeps a cache for a few seconds. Avoids stress on the database with the
        successive streams observerd on this query

        Raises:
            web.HTTPServiceUnavailable: if database raises an exception
        """
        try:
            return await get_active_user_or_none(get_database_engine(self._app), email)
        except DatabaseError as err:
            raise web.HTTPServiceUnavailable(
                reason="Authentication service is temporary unavailable"
            ) from err

    @property
    def access_model(self) -> RoleBasedAccessModel:
        return self._access_model

    async def clear_cache(self):
        autz_cache: BaseCache = self._get_auth_or_none.cache
        await autz_cache.clear()

    #
    # AbstractAuthorizationPolicy API
    #

    async def authorized_userid(self, identity: IdentityStr) -> int | None:
        """Implements Inteface: Retrieve authorized user id.

        Return the user_id of the user identified by the identity
        or "None" if no user exists related to the identity.
        """
        user_info: AuthInfoDict | None = await self._get_auth_or_none(identity)

        if user_info is None:
            return None

        user_id: int = user_info["id"]
        return user_id

    async def permits(
        self,
        identity: IdentityStr,
        permission: str,
        context: OptionalContext = None,
    ) -> bool:
        """Implements Interface: Determines whether an identified user has permission

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

        auth_info = await self._get_auth_or_none(identity)
        if auth_info is None:
            return False

        # role-based access
        return await check_access(
            self._access_model,
            role=auth_info["role"],
            operations=permission,
            context=context,
        )
