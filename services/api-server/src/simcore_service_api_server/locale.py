"""Per-request locale resolution for the api-server.

Locale precedence (highest → lowest):
    1. ``X-App-Locale`` request header (set explicitly by the front-end/client).
    2. ``Accept-Language`` header (first tag, normalised to gettext form).
    3. ``"en"`` — hard default.

The middleware is only registered when ``API_SERVER_I18N=1`` in settings.
When it does not run, exception handlers fall back to ``DEFAULT_LOCALE`` via
``getattr(request.state, "locale", DEFAULT_LOCALE)``.
"""

from typing import Final

from common_library.i18n import DEFAULT_LOCALE, normalize_locale
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

_X_APP_LOCALE_HEADER: Final[str] = "X-App-Locale"
_ACCEPT_LANGUAGE_HEADER: Final[str] = "Accept-Language"


class LocaleMiddleware(BaseHTTPMiddleware):
    """Reads locale from request headers and stores it in ``request.state.locale``."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        for header in (_X_APP_LOCALE_HEADER, _ACCEPT_LANGUAGE_HEADER):
            if raw := request.headers.get(header):
                request.state.locale = normalize_locale(raw)
                break
        else:
            request.state.locale = DEFAULT_LOCALE
        return await call_next(request)
