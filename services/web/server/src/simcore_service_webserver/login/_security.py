""" Utils that extends on security_api plugin

"""
import logging
from typing import Any

from aiohttp import web
from servicelib.logging_utils import get_log_record_extra, log_context

from ..security.api import remember
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
    user_id = user.get("id")
    with log_context(
        log,
        logging.INFO,
        "login of user_id=%s with %s",
        f"{user_id}",
        f"{email=}",
        extra=get_log_record_extra(user_id=user_id),
    ):
        response = flash_response(MSG_LOGGED_IN, "INFO")
        await remember(
            request=request,
            response=response,
            identity=email,
        )
        return response
