"""Per-request locale resolution for the web-server.

Locale precedence (highest → lowest):
    1. ``X-App-Locale`` request header (set explicitly by the front-end).
    2. ``Accept-Language`` header (first tag, normalised to gettext form).
    3. ``"en"`` — hard default.

The DB-stored ``LocaleUserPreference`` is NOT read inside the middleware to
avoid an async DB call on every request.  Code paths that need the persisted
preference (e.g. email rendering) should call ``get_user_locale`` directly.
"""

from typing import Final

from aiohttp import web
from common_library.i18n import DEFAULT_LOCALE, normalize_locale
from servicelib.aiohttp.typing_extension import Handler

from .user_preferences._models import LocaleUserPreference
from .user_preferences.user_preferences_service import get_frontend_user_preference

RQ_LOCALE_KEY: Final[str] = f"{__name__}.locale"

_X_APP_LOCALE_HEADER: Final[str] = "X-App-Locale"


def get_request_locale(request: web.Request) -> str:
    """Return the locale resolved for this request (set by the locale middleware).

    Falls back to header-based resolution if the middleware did not run (e.g.
    in unit tests that don't register the full middleware stack).
    """
    if (locale := request.get(RQ_LOCALE_KEY)) is not None:
        return locale
    return _resolve_from_headers(request)


def _resolve_from_headers(request: web.Request) -> str:
    if raw := request.headers.get(_X_APP_LOCALE_HEADER):
        return normalize_locale(raw)
    if raw := request.headers.get("Accept-Language"):
        return normalize_locale(raw)
    return DEFAULT_LOCALE


@web.middleware
async def locale_middleware(request: web.Request, handler: Handler) -> web.StreamResponse:
    """Resolves locale from request headers and stores it in ``request[RQ_LOCALE_KEY]``."""
    request[RQ_LOCALE_KEY] = _resolve_from_headers(request)
    return await handler(request)


async def get_user_locale(
    app: web.Application,
    *,
    user_id: int,
    product_name: str,
) -> str:
    """Look up the user's persisted ``LocaleUserPreference`` and return the locale string.

    Falls back to ``DEFAULT_LOCALE`` when no preference has been saved.
    Intended for use in background / non-request code (e.g. email dispatch).
    """
    pref = await get_frontend_user_preference(
        app,
        user_id=user_id,
        product_name=product_name,
        preference_class=LocaleUserPreference,
    )
    if pref is not None and pref.value:
        return pref.value
    return DEFAULT_LOCALE
