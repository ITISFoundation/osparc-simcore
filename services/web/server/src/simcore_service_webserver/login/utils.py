import logging
import random
from typing import Any, Optional

import attr
import passlib.hash
from aiohttp import web
from models_library.users import UserID
from passlib import pwd
from servicelib import observer
from servicelib.aiohttp.rest_models import LogMessageType
from servicelib.json_serialization import json_dumps
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON
from simcore_postgres_database.models.users import UserRole

from ..db_models import ConfirmationAction, UserRole, UserStatus
from ._constants import MSG_ACTIVATION_REQUIRED, MSG_USER_BANNED, MSG_USER_EXPIRED

log = logging.getLogger(__name__)


def _to_names(enum_cls, names):
    """ensures names are in enum be retrieving each of them"""
    # FIXME: with asyncpg need to user NAMES
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


async def notify_user_logout(
    app: web.Application, user_id: UserID, client_session_id: Optional[Any] = None
):
    """Broadcasts logout of 'user_id' in 'client_session_id'.

    If 'client_session_id' is None, then all sessions are considered

    Listeners (e.g. sockets) will trigger logout mechanisms
    """
    await observer.emit("SIGNAL_USER_LOGOUT", user_id, client_session_id, app)


def encrypt_password(password: str) -> str:
    # TODO: add settings sha256_crypt.using(**settings).hash(secret)
    # see https://passlib.readthedocs.io/en/stable/lib/passlib.hash.sha256_crypt.html
    #
    return passlib.hash.sha256_crypt.using(rounds=1000).hash(password)


def check_password(password: str, password_hash: str) -> bool:
    return passlib.hash.sha256_crypt.verify(password, password_hash)


def get_random_string(min_len: int, max_len: Optional[int] = None) -> str:
    max_len = max_len or min_len
    size = random.randint(min_len, max_len)
    return pwd.genword(entropy=52, length=size)


def get_client_ip(request: web.Request) -> str:
    try:
        ips = request.headers["X-Forwarded-For"]
    except KeyError:
        ips = request.transport.get_extra_info("peername")[0]
    return ips.split(",")[0]


def flash_response(
    message: str, level: str = "INFO", *, status: int = web.HTTPOk.status_code
) -> web.Response:
    response = envelope_response(
        attr.asdict(LogMessageType(message, level)),
        status=status,
    )
    return response


def envelope_response(
    data: Any, *, status: int = web.HTTPOk.status_code
) -> web.Response:
    response = web.json_response(
        {
            "data": data,
            "error": None,
        },
        dumps=json_dumps,
        status=status,
    )
    return response
