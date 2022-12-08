""" Utils that extends on security_api plugin

"""
import logging
from typing import Any

from aiohttp import web
from servicelib.logging_utils import log_context

from ..security_api import remember
from ..session import get_session
from ._constants import MSG_LOGGED_IN
from .utils import flash_response

log = logging.getLogger(__name__)


async def login_granted_response(
    request: web.Request, *, user: dict[str, Any]
) -> web.Response:
    """
    Grants authorization for user creating a responses with an auth cookie

    NOTE: All handlers with @login_required needs this cookie!

    Uses security API
    """
    email = user["email"]
    with log_context(
        log,
        logging.INFO,
        "login of user_id=%s with %s",
        f"{user.get('id')}",
        f"{email=}",
    ):
        response = flash_response(MSG_LOGGED_IN, "INFO")
        await remember(
            request=request,
            response=response,
            identity=email,
        )
        return response


# TODO: should be valid for a limited time or
# a countdown to limit the number of times
_ONE_TIME_ACCESS_FORMAT = "one_time_access.{}"


async def grant_one_time_access(
    request: web.Request,
    handler_name: str,
    identity: str,
):
    session = await get_session(request)
    session[_ONE_TIME_ACCESS_FORMAT.format(handler_name)] = identity


async def check_one_time_access_and_consume(
    request: web.Request, handler_name: str, identity: str
):
    session_key = _ONE_TIME_ACCESS_FORMAT.format(handler_name)
    session = await get_session(request)
    granted = session.get(session_key)

    if not granted or granted != identity:
        raise web.HTTPUnauthorized(
            reason="Can only resend 2FA during login or registration"
        )
    del session[session_key]
