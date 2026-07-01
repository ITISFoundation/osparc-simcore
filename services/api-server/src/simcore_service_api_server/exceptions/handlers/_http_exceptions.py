from common_library.gettext_support import DEFAULT_LOCALE, get_translator
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse

from ._utils import create_error_json_response


async def http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    assert request  # nosec
    assert isinstance(exc, HTTPException)  # nosec

    # NOTE: LocaleMiddleware only active with API_SERVER_LOCALIZED_MESSAGES_ENABLED=1
    locale = getattr(request.state, "locale", DEFAULT_LOCALE)
    error_msg = get_translator(locale).gettext(exc.detail) if isinstance(exc.detail, str) else exc.detail

    return create_error_json_response(error_msg, status_code=exc.status_code)
