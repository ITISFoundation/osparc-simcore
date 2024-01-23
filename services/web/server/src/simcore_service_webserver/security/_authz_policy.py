""" AUTHoriZation (auth) policy:
"""
import logging
from typing import Final

from aiocache import cached
from aiocache.base import BaseCache
from aiohttp import web
from aiohttp_security.abc import AbstractAuthorizationPolicy
from pydantic import ValidationError
from simcore_postgres_database.errors import DatabaseError

from ..db.plugin import get_database_engine
from ._authz_access_model import OptionalContext, RoleBasedAccessModel, check_access
from ._authz_db import AuthInfoDict, get_active_user_or_none
from ._constants import MSG_AUTH_NOT_AVAILABLE
from ._identity_api import IdentityStr, VerifiedIdentity

_logger = logging.getLogger(__name__)

_SECOND = 1  # in seconds
_ACTIVE_USER_AUTHZ_CACHE_TTL: Final = 5 * _SECOND


class AuthorizationPolicy(AbstractAuthorizationPolicy):
    def __init__(self, app: web.Application, access_model: RoleBasedAccessModel):
        self._app = app
        self._access_model = access_model

    @cached(
        ttl=_ACTIVE_USER_AUTHZ_CACHE_TTL,
        namespace=__name__,
        key_builder=lambda f, *ag, **kw: f"{f.__name__}/{kw['email']}",
    )
    async def _get_auth_or_none(self, *, email: str) -> AuthInfoDict | None:
        """Keeps a cache for a few seconds. Avoids stress on the database with the
        successive streams observerd on this query

        Raises:
            web.HTTPServiceUnavailable: if database raises an exception
        """
        try:
            return await get_active_user_or_none(get_database_engine(self._app), email)
        except DatabaseError as err:
            _logger.exception("Auth unavailable due to database error")
            raise web.HTTPServiceUnavailable(reason=MSG_AUTH_NOT_AVAILABLE) from err

    @property
    def access_model(self) -> RoleBasedAccessModel:
        return self._access_model

    async def clear_cache(self):
        # pylint: disable=no-member
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
        try:
            vi = VerifiedIdentity.parse_raw(identity)
        except ValidationError:
            return None
        else:
            user_info: AuthInfoDict | None = None
            # FIXME: needs to include product_name in auth query!
            user_info = await self._get_auth_or_none(email=vi.email)
            return user_info["id"] if user_info else None

    async def permits(
        self,
        identity: IdentityStr,
        permission: str,
        context: OptionalContext = None,
    ) -> bool:
        """Implements Interface: Determines whether an identified user has permission

        :param identity: session identified corresponds to the user's email as defined in login.handlers_registration
        :param permission: name of the operation that user wants to execute
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

        auth_info = await self._get_auth_or_none(email=identity)
        if auth_info is None:
            return False

        # role-based access
        return await check_access(
            self._access_model,
            role=auth_info["role"],
            operations=permission,
            context=context,
        )
