import functools
import logging

from aiohttp import web
from servicelib.aiohttp.typing_extension import Handler
from servicelib.logging_errors import create_troubleshootting_log_kwargs
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON

from ..errors import WebServerBaseError
from ._constants import MSG_2FA_UNAVAILABLE

_logger = logging.getLogger(__name__)


class LoginError(WebServerBaseError, ValueError): ...


class SendingVerificationSmsError(LoginError):
    msg_template = "Sending verification sms failed. {reason}"


class SendingVerificationEmailError(LoginError):
    msg_template = "Sending verification email failed. {reason}"


def handle_login_exceptions(handler: Handler):
    @functools.wraps(handler)
    async def wrapper(request: web.Request) -> web.StreamResponse:
        try:
            return await handler(request)

        except (SendingVerificationSmsError, SendingVerificationEmailError) as exc:
            error_code = exc.error_code()
            front_end_msg = MSG_2FA_UNAVAILABLE
            # in these cases I want to log the cause
            _logger.exception(
                **create_troubleshootting_log_kwargs(
                    front_end_msg,
                    error=exc,
                    error_code=error_code,
                )
            )
            raise web.HTTPServiceUnavailable(
                text=front_end_msg,
                content_type=MIMETYPE_APPLICATION_JSON,
            ) from exc

    return wrapper
