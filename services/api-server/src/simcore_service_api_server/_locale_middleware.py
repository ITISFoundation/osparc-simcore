"""Per-request locale resolution for the api-server.

Locale precedence (highest → lowest):
    1. ``X-Simcore-Language`` request header (set explicitly by the front-end/client).
    2. ``Accept-Language`` header (first tag, normalised to gettext form).
    3. ``"en"`` — hard default.

The middleware is only registered when ``API_SERVER_LOCALIZED_MESSAGES_ENABLED=1`` in settings.
When it does not run, exception handlers fall back to ``DEFAULT_LOCALE`` via
``getattr(request.state, "locale", DEFAULT_LOCALE)``.
"""

from common_library.gettext_support import DEFAULT_LOCALE, normalize_locale
from servicelib.common_headers import X_SIMCORE_LANGUAGE
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

_ACCEPT_LANGUAGE_HEADER = "Accept-Language"


class LocaleMiddleware(BaseHTTPMiddleware):
    """Reads locale from request headers and stores it in ``request.state.locale``."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        for header in (X_SIMCORE_LANGUAGE, _ACCEPT_LANGUAGE_HEADER):
            if raw := request.headers.get(header):
                request.state.locale = normalize_locale(raw)
                break
        else:
            request.state.locale = DEFAULT_LOCALE
        return await call_next(request)
