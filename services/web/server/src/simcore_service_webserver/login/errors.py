import functools

from aiohttp import web
from servicelib.aiohttp.typing_extension import Handler
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON

from ..errors import WebServerBaseError
from ._constants import MSG_2FA_UNAVAILABLE_OEC


class LoginError(WebServerBaseError, ValueError):
    ...


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
            raise web.HTTPServiceUnavailable(
                reason=MSG_2FA_UNAVAILABLE_OEC.format(error_code=exc.code),
                content_type=MIMETYPE_APPLICATION_JSON,
            ) from exc

    return wrapper
