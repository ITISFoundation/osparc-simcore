from typing import Any

from aiohttp import web
from models_library.products import ProductName
from models_library.users import UserID
from pydantic import PositiveInt
from servicelib.aiohttp import observer
from simcore_postgres_database.models.users import UserRole

from ..db.models import ConfirmationAction, UserStatus
from .constants import (
    MSG_ACTIVATION_REQUIRED,
    MSG_USER_BANNED,
    MSG_USER_DELETED,
    MSG_USER_EXPIRED,
)


def _to_names(enum_cls, names) -> list[str]:
    """ensures names are in enum be retrieving each of them"""
    return [getattr(enum_cls, att).name for att in names.split()]


CONFIRMATION_PENDING, ACTIVE, BANNED, EXPIRED, DELETED = (
    UserStatus.CONFIRMATION_PENDING.name,
    UserStatus.ACTIVE.name,
    UserStatus.BANNED.name,
    UserStatus.EXPIRED.name,
    UserStatus.DELETED.name,
)
_EXPECTED_ENUMS = 5
assert len(UserStatus) == _EXPECTED_ENUMS  # nosec


ANONYMOUS, GUEST, USER, TESTER = _to_names(UserRole, "ANONYMOUS GUEST USER TESTER")

REGISTRATION, RESET_PASSWORD, CHANGE_EMAIL = _to_names(
    ConfirmationAction, "REGISTRATION RESET_PASSWORD CHANGE_EMAIL"
)


def validate_user_status(*, user_status: str, user_role: str, support_email: str):
    """

    Raises:
        web.HTTPUnauthorized
    """

    if user_status == DELETED:
        raise web.HTTPUnauthorized(
            text=MSG_USER_DELETED.format(support_email=support_email),
        )  # 401

    if user_status == BANNED or user_role == ANONYMOUS:
        raise web.HTTPUnauthorized(
            text=MSG_USER_BANNED.format(support_email=support_email),
        )  # 401

    if user_status == EXPIRED:
        raise web.HTTPUnauthorized(
            text=MSG_USER_EXPIRED.format(support_email=support_email),
        )  # 401

    if user_status == CONFIRMATION_PENDING:
        raise web.HTTPUnauthorized(
            text=MSG_ACTIVATION_REQUIRED,
        )  # 401

    assert user_status == ACTIVE  # nosec


async def notify_user_confirmation(
    app: web.Application,
    user_id: UserID,
    product_name: ProductName,
    extra_credits_in_usd: PositiveInt | None,
):
    """Broadcast that user with 'user_id' has login for the first-time in 'product_name'"""
    # NOTE: Follow up in https://github.com/ITISFoundation/osparc-simcore/issues/4822
    await observer.emit(
        app,
        "SIGNAL_ON_USER_CONFIRMATION",
        user_id=user_id,
        product_name=product_name,
        extra_credits_in_usd=extra_credits_in_usd,
    )


async def notify_user_logout(
    app: web.Application, user_id: UserID, client_session_id: Any | None = None
):
    """Broadcasts logout of 'user_id' in 'client_session_id'.

    If 'client_session_id' is None, then all sessions are considered

    Listeners (e.g. sockets) will trigger logout mechanisms
    """
    await observer.emit(
        app,
        "SIGNAL_USER_LOGOUT",
        user_id,
        client_session_id,
        app,
    )
