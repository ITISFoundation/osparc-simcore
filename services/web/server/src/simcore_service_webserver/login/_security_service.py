"""Utils that extends on security_api plugin"""

import logging

from aiohttp import web
from common_library.logging.logging_base import get_log_record_extra
from servicelib.logging_utils import log_context

from ..locale import translate_message
from ..security import security_web
from ..web_utils import flash_response
from ._auth_service import UserInfoDict
from .constants import MSG_LOGGED_IN

_logger = logging.getLogger(__name__)


async def login_granted_response(request: web.Request, *, user: UserInfoDict) -> web.Response:
    """
    Grants authorization for user creating a responses with an auth cookie

    NOTE: All handlers with @login_required needs this cookie!

    Uses security API
    """

    email = user["email"]
    user_id = user.get("id")

    with log_context(
        _logger,
        logging.INFO,
        f"login of {user_id=} with {email=}",
        extra=get_log_record_extra(user_id=user_id),
    ):
        response = flash_response(translate_message(MSG_LOGGED_IN, request), "INFO")
        return await security_web.remember_identity(
            request=request,
            response=response,
            user_email=email,
        )
