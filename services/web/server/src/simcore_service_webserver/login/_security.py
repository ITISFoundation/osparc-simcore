""" Utils that extends on security_api plugin

"""
import logging
from typing import Any

from aiohttp import web
from servicelib.logging_utils import log_context

from ..security_api import remember
from .settings import LoginOptions
from .utils import flash_response

log = logging.getLogger(__name__)


async def authorize_login(
    request: web.Request, user: dict[str, Any], cfg: LoginOptions
):
    """
    Uses security API to authorize authenticated user
    """
    email = user["email"]
    with log_context(
        log,
        logging.INFO,
        "login of user_id=%s with %s",
        f"{user.get('id')}",
        f"{email=}",
    ):
        rsp = flash_response(cfg.MSG_LOGGED_IN, "INFO")
        await remember(
            request=request,
            response=rsp,
            identity=email,
        )
        return rsp
