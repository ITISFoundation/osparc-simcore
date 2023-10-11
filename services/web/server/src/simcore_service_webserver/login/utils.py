import logging
import random
from dataclasses import asdict
from typing import Any, cast

import passlib.hash
from aiohttp import web
from models_library.products import ProductName
from models_library.users import UserID
from passlib import pwd
from pydantic import PositiveInt
from servicelib.aiohttp import observer
from servicelib.aiohttp.rest_models import LogMessageType
from servicelib.json_serialization import json_dumps
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON
from simcore_postgres_database.models.users import UserRole

from ..db.models import ConfirmationAction, UserStatus
from ._constants import MSG_ACTIVATION_REQUIRED, MSG_USER_BANNED, MSG_USER_EXPIRED

log = logging.getLogger(__name__)


def _to_names(enum_cls, names):
    """ensures names are in enum be retrieving each of them"""
    return [getattr(enum_cls, att).name for att in names.split()]


CONFIRMATION_PENDING, ACTIVE, BANNED, EXPIRED = (
    UserStatus.CONFIRMATION_PENDING.name,
    UserStatus.ACTIVE.name,
    UserStatus.BANNED.name,
    UserStatus.EXPIRED.name,
)
assert len(UserStatus) == 4  # nosec


ANONYMOUS, GUEST, USER, TESTER = _to_names(UserRole, "ANONYMOUS GUEST USER TESTER")

REGISTRATION, RESET_PASSWORD, CHANGE_EMAIL = _to_names(
    ConfirmationAction, "REGISTRATION RESET_PASSWORD CHANGE_EMAIL"
)


def validate_user_status(*, user: dict, support_email: str):
    user_status: str = user["status"]

    if user_status == BANNED or user["role"] == ANONYMOUS:
        raise web.HTTPUnauthorized(
            reason=MSG_USER_BANNED.format(support_email=support_email),
            content_type=MIMETYPE_APPLICATION_JSON,
        )  # 401

    if user_status == EXPIRED:
        raise web.HTTPUnauthorized(
            reason=MSG_USER_EXPIRED.format(support_email=support_email),
            content_type=MIMETYPE_APPLICATION_JSON,
        )  # 401

    if user_status == CONFIRMATION_PENDING:
        raise web.HTTPUnauthorized(
            reason=MSG_ACTIVATION_REQUIRED,
            content_type=MIMETYPE_APPLICATION_JSON,
        )  # 401

    assert user_status == ACTIVE  # nosec


async def notify_user_confirmation(
    app: web.Application,
    user_id: UserID,
    product_name: ProductName,
    extra_credits: PositiveInt | None,
):
    """Broadcast that user with 'user_id' has login for the first-time in 'product_name'"""
    # NOTE: Follow up in https://github.com/ITISFoundation/osparc-simcore/issues/4822
    await observer.emit(
        app,
        "SIGNAL_ON_USER_CONFIRMATION",
        user_id=user_id,
        product_name=product_name,
        extra_credits=extra_credits,
    )


async def notify_user_logout(
    app: web.Application, user_id: UserID, client_session_id: Any | None = None
):
    """Broadcasts logout of 'user_id' in 'client_session_id'.

    If 'client_session_id' is None, then all sessions are considered

    Listeners (e.g. sockets) will trigger logout mechanisms
    """
    await observer.emit(app, "SIGNAL_USER_LOGOUT", user_id, client_session_id, app)


def encrypt_password(password: str) -> str:
    # SEE https://github.com/ITISFoundation/osparc-simcore/issues/3375
    return cast(str, passlib.hash.sha256_crypt.using(rounds=1000).hash(password))


def check_password(password: str, password_hash: str) -> bool:
    return cast(bool, passlib.hash.sha256_crypt.verify(password, password_hash))


def get_random_string(min_len: int, max_len: int | None = None) -> str:
    max_len = max_len or min_len
    size = random.randint(min_len, max_len)  # noqa: S311 # nosec # NOSONAR
    return cast(str, pwd.genword(entropy=52, length=size))


def get_client_ip(request: web.Request) -> str:
    try:
        ips = request.headers["X-Forwarded-For"]
    except KeyError:
        ips = request.transport.get_extra_info("peername")[0]
    return cast(str, ips.split(",")[0])


def flash_response(
    message: str, level: str = "INFO", *, status: int = web.HTTPOk.status_code
) -> web.Response:
    return envelope_response(
        data=asdict(LogMessageType(message, level)),
        status=status,
    )


def envelope_response(
    data: Any, *, status: int = web.HTTPOk.status_code
) -> web.Response:
    return web.json_response(
        {
            "data": data,
            "error": None,
        },
        dumps=json_dumps,
        status=status,
    )
