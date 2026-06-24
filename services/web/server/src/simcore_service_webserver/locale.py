"""Per-request locale resolution for the web-server.

Locale precedence (highest → lowest):
    1. ``X-App-Locale`` request header (set explicitly by the front-end).
    2. ``Accept-Language`` header (first tag, normalised to gettext form).
    3. ``"en"`` — hard default.

The DB-stored ``LocaleUserPreference`` is NOT read inside the middleware to
avoid an async DB call on every request.  Code paths that need the persisted
preference (e.g. email rendering) should call ``get_user_locale`` directly.

The middleware is gated on ``WEBSERVER_I18N``.  When the flag is off the key
is still written (as DEFAULT_LOCALE) so downstream code never needs to guard
against a missing ``RQ_LOCALE_KEY``.
"""

from typing import Final

from aiohttp import web
from common_library.i18n import DEFAULT_LOCALE, normalize_locale
from servicelib.aiohttp.typing_extension import Handler

from .application_keys import APP_SETTINGS_APPKEY
from .user_preferences._models import LocaleUserPreference
from .user_preferences.user_preferences_service import get_frontend_user_preference

RQ_LOCALE_KEY: Final[str] = f"{__name__}.locale"

_X_APP_LOCALE_HEADER: Final[str] = "X-App-Locale"


@web.middleware
async def locale_middleware(request: web.Request, handler: Handler) -> web.StreamResponse:
    """Resolves locale from request headers and stores it in ``request[RQ_LOCALE_KEY]``."""
    settings = request.app[APP_SETTINGS_APPKEY]
    if settings.WEBSERVER_I18N:
        for header in (_X_APP_LOCALE_HEADER, "Accept-Language"):
            if raw := request.headers.get(header):
                request[RQ_LOCALE_KEY] = normalize_locale(raw)
                break
        else:
            request[RQ_LOCALE_KEY] = DEFAULT_LOCALE
    else:
        request[RQ_LOCALE_KEY] = DEFAULT_LOCALE
    return await handler(request)


locale_middleware.__middleware_name__ = f"{__name__}.locale_middleware"  # type: ignore[attr-defined]


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
        return str(pref.value)
    return DEFAULT_LOCALE
