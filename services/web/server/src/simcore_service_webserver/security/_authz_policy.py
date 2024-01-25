""" AUTHoriZation (auth) policy:
"""
import functools
import logging
from typing import Callable, Final

from aiocache import cached
from aiocache.base import BaseCache
from aiohttp import web
from aiohttp_security.abc import AbstractAuthorizationPolicy
from models_library.products import ProductName
from models_library.users import UserID
from simcore_postgres_database.errors import DatabaseError

from ..db.plugin import get_database_engine
from ._authz_access_model import (
    AuthContextDict,
    OptionalContext,
    RoleBasedAccessModel,
    has_access_by_role,
)
from ._authz_db import AuthInfoDict, get_active_user_or_none, is_user_in_product_name
from ._constants import MSG_AUTH_NOT_AVAILABLE
from ._identity_api import IdentityStr

_logger = logging.getLogger(__name__)

_SECOND = 1  # in seconds
_ACTIVE_USER_AUTHZ_CACHE_TTL: Final = 5 * _SECOND


def _handle_exceptions_as_503(coro: Callable):
    @functools.wraps(coro)
    async def _wrapper(self, **kwargs):
        try:
            return await coro(self, **kwargs)
        except DatabaseError as err:
            _logger.exception("Auth unavailable due to database error")
            raise web.HTTPServiceUnavailable(reason=MSG_AUTH_NOT_AVAILABLE) from err

    return _wrapper


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

    @_handle_exceptions_as_503
    async def _has_access_to_product(
        self, *, user_id: UserID, product_name: ProductName
    ) -> bool:
        return await is_user_in_product_name(
            get_database_engine(self._app), user_id, product_name
        )

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
        user_info: AuthInfoDict | None = await self._get_auth_or_none(email=identity)
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

        context = context or AuthContextDict()

        # product access
        if permission == "product":
            product_name = context.get("product_name")
            if product_name is None:
                return False
            return await self._has_access_to_product(
                user_id=auth_info["id"], product_name=product_name
            )

        # role-based access
        return await has_access_by_role(
            self._access_model,
            role=auth_info["role"],
            operations=permission,
            context=context,
        )
