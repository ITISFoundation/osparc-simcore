""" AUTHoriZation (auth) policy:
"""
import logging

from aiohttp import web
from aiohttp_security.abc import AbstractAuthorizationPolicy
from expiringdict import ExpiringDict

from ..db.plugin import get_database_engine
from ._authz_access_model import OptionalContext, RoleBasedAccessModel, check_access
from ._authz_db import UserInfoDict, get_active_user_or_none
from ._identity import IdentityStr

_logger = logging.getLogger(__name__)


class AuthorizationPolicy(AbstractAuthorizationPolicy):
    def __init__(self, app: web.Application, access_model: RoleBasedAccessModel):
        self._app = app
        self._access_model = access_model
        self._cache = ExpiringDict(max_len=100, max_age_seconds=10)

    async def _get_user_info(self, email: IdentityStr) -> UserInfoDict | None:
        # NOTE: Keeps a cache for a few seconds. Observed successive streams of this query
        user: UserInfoDict | None = self._cache.get(email, None, with_age=False)
        if user is None:
            user = await get_active_user_or_none(get_database_engine(self._app), email)
            if user:
                assert user["id"]  # nosec
                assert user["role"]  # nosec
                self._cache[email] = user

        return user

    @property
    def access_model(self) -> RoleBasedAccessModel:
        return self._access_model

    def clear_cache(self):
        self._cache.clear()

    async def authorized_userid(self, identity: IdentityStr) -> int | None:
        """Implements Inteface: Retrieve authorized user id.

        Return the user_id of the user identified by the identity
        or "None" if no user exists related to the identity.
        """
        user_info: UserInfoDict | None = await self._get_user_info(identity)

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

        user_info = await self._get_user_info(identity)
        if user_info is None:
            return False

        # role-based access
        return await check_access(
            self._access_model,
            role=user_info["role"],
            operations=permission,
            context=context,
        )
