"""AUTHoriZation (auth) policy"""

import contextlib
import logging
from typing import Final

from aiocache import cached  # type: ignore[import-untyped]
from aiocache.base import BaseCache  # type: ignore[import-untyped]
from aiohttp import web
from aiohttp_security.abc import (  # type: ignore[import-untyped]
    AbstractAuthorizationPolicy,
)
from common_library.users_enums import UserRole
from models_library.products import ProductName
from models_library.users import UserID
from servicelib.aiohttp.db_asyncpg_engine import get_async_engine
from servicelib.logging_errors import create_troubleshooting_log_kwargs
from simcore_postgres_database.aiopg_errors import DatabaseError as AiopgDatabaseError
from sqlalchemy.exc import DatabaseError as SQLAlchemyDatabaseError

from . import _authz_repository
from ._authz_access_model import (
    AuthContextDict,
    OptionalContext,
    RoleBasedAccessModel,
    has_access_by_role,
)
from ._authz_access_roles import NAMED_GROUP_PERMISSIONS
from ._authz_repository import ActiveUserIdAndRole
from ._constants import MSG_AUTH_NOT_AVAILABLE, PERMISSION_PRODUCT_LOGIN_KEY
from ._identity_web import IdentityStr

_logger = logging.getLogger(__name__)

_SECOND = 1  # in seconds
_MINUTE: Final = 60 * _SECOND
_AUTHZ_BURST_CACHE_TTL: Final = (
    # WARNING: TLL=0 means it never expires
    # Rationale:
    #   a user's access to a product does not change that frequently
    #   Keeps a cache during bursts to avoid stress on the database
    30
    * _MINUTE
)


@contextlib.contextmanager
def _handle_exceptions_as_503():
    try:
        yield
    except (AiopgDatabaseError, SQLAlchemyDatabaseError) as err:
        _logger.exception(
            **create_troubleshooting_log_kwargs(
                "Auth unavailable due to database error",
                error=err,
                tip="Check database connection",
            )
        )

        raise web.HTTPServiceUnavailable(text=MSG_AUTH_NOT_AVAILABLE) from err


class AuthorizationPolicy(AbstractAuthorizationPolicy):
    def __init__(self, app: web.Application, access_model: RoleBasedAccessModel):
        self._app = app
        self._access_model = access_model

    @cached(
        ttl=_AUTHZ_BURST_CACHE_TTL,
        namespace=__name__,
        key_builder=lambda f, *ag, **kw: f"{f.__name__}/{kw['email']}",
    )
    async def _get_authorized_user_or_none(
        self, *, email: str
    ) -> ActiveUserIdAndRole | None:
        """
        Raises:
            web.HTTPServiceUnavailable: if database raises an exception
        """
        with _handle_exceptions_as_503():
            return await _authz_repository.get_active_user_or_none(
                get_async_engine(self._app), email=email
            )

    @cached(
        ttl=_AUTHZ_BURST_CACHE_TTL,
        namespace=__name__,
        key_builder=lambda f, *ag, **kw: f"{f.__name__}/{kw['user_id']}/{kw['product_name']}",
    )
    async def _has_access_to_product(
        self, *, user_id: UserID, product_name: ProductName
    ) -> bool:
        """
        Raises:
            web.HTTPServiceUnavailable: if database raises an exception
        """
        with _handle_exceptions_as_503():
            return await _authz_repository.is_user_in_product_name(
                get_async_engine(self._app), user_id=user_id, product_name=product_name
            )

    @cached(
        ttl=_AUTHZ_BURST_CACHE_TTL,
        namespace=__name__,
        key_builder=lambda f, *ag, **kw: f"{f.__name__}/{kw['user_id']}/{kw['group_id']}",
    )
    async def _is_user_in_group(self, *, user_id: UserID, group_id: int) -> bool:
        """
        Raises:
            web.HTTPServiceUnavailable: if database raises an exception
        """
        with _handle_exceptions_as_503():
            return await _authz_repository.is_user_in_group(
                get_async_engine(self._app), user_id=user_id, group_id=group_id
            )

    @property
    def access_model(self) -> RoleBasedAccessModel:
        return self._access_model

    async def clear_cache(self):
        # pylint: disable=no-member
        for fun in (
            self._get_authorized_user_or_none,
            self._has_access_to_product,
            self._is_user_in_group,
        ):
            autz_cache: BaseCache = fun.cache
            await autz_cache.clear()

    #
    # AbstractAuthorizationPolicy API
    #

    async def authorized_userid(self, identity: IdentityStr) -> int | None:
        """Implements Inteface: Retrieve authorized user id.

        Return the user_id of the user identified by the identity
        or "None" if no user exists related to the identity.
        """
        user_info: ActiveUserIdAndRole | None = await self._get_authorized_user_or_none(
            email=identity
        )
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
            return False

        # authorized user info
        authorized_user_info = await self._get_authorized_user_or_none(email=identity)
        if authorized_user_info is None:
            return False

        user_id = authorized_user_info["id"]
        user_role = authorized_user_info["role"]

        # context info: product_name
        context = context or AuthContextDict()
        product_name = context.get("product_name")

        assert user_id == context.get(  # nosec
            "authorized_uid"
        ), f"{user_id}!={context.get('authorized_uid')}"

        # PRODUCT access
        if permission == PERMISSION_PRODUCT_LOGIN_KEY:
            ok: bool = product_name is not None and await self._has_access_to_product(
                user_id=user_id, product_name=product_name
            )
            return ok

        # ROLE-BASED access policy
        role_allowed = await has_access_by_role(
            self._access_model,
            role=user_role,
            operation=permission,
            context=context,
        )

        if role_allowed:
            return True

        # GROUP-BASED access policy (only if enabled in context and user is above GUEST role)
        product_support_group_id = context.get("product_support_group_id", None)
        group_allowed = (
            product_support_group_id is not None
            and user_role > UserRole.GUEST
            and permission in NAMED_GROUP_PERMISSIONS.get("PRODUCT_SUPPORT_GROUP", [])
            and await self._is_user_in_group(
                user_id=user_id, group_id=product_support_group_id
            )
        )

        return group_allowed  # noqa: RET504
