"""Per-request locale resolution for the web-server.

Locale precedence (highest → lowest):
    1. ``X-Simcore-Language`` request header (set explicitly by the front-end).
    2. ``Accept-Language`` header (first tag, normalised to gettext form).
    3. ``"en"`` — hard default.

The DB-stored ``users.language`` (a per-user profile field, not a per-product
preference) is NOT read inside the middleware to avoid an async DB call on
every request.  Code paths that need the persisted language (e.g. email
rendering) should call ``get_user_locale`` directly.

The middleware is gated on ``WEBSERVER_LOCALIZED_MESSAGES_ENABLED``.  When the flag is off the key
is still written (as DEFAULT_LOCALE) so downstream code never needs to guard
against a missing ``RQ_LOCALE_KEY``.
"""

from typing import Final

from aiohttp import web
from common_library.gettext_support import DEFAULT_LOCALE, SupportedLocale, get_translator, normalize_locale
from models_library.groups import GroupID
from models_library.users import UserID
from servicelib.aiohttp.typing_extension import Handler
from servicelib.common_headers import X_SIMCORE_LANGUAGE

from .application_keys import APP_SETTINGS_APPKEY
from .users import users_service

RQ_LOCALE_KEY: Final[str] = f"{__name__}.locale"

_ACCEPT_LANGUAGE_HEADER: Final[str] = "Accept-Language"


def translate_message(message: str, request: web.Request) -> str:
    """Translate a user_message()-marked string to the request locale."""
    return get_translator(request.get(RQ_LOCALE_KEY, DEFAULT_LOCALE)).gettext(message)


def get_locale_or_none(request: web.Request) -> SupportedLocale | None:
    """Equivalent to "Does the requests ask for a specific locale or not?"

    Returns the locale resolved by ``locale_middleware`` for this request, or ``None``
    if the middleware did not run (e.g. the request key is missing).

    Useful for passing an optional override (e.g. to
    ``notifications_service.send_message_from_template``) that should defer to the recipient's
    DB-stored language (see ``get_user_locale``) when no request-resolved locale is available.
    """
    return request.get(RQ_LOCALE_KEY)


@web.middleware
async def locale_middleware(request: web.Request, handler: Handler) -> web.StreamResponse:
    """Resolves locale from request headers and stores it in ``request[RQ_LOCALE_KEY]``."""
    settings = request.app[APP_SETTINGS_APPKEY]
    if settings.WEBSERVER_LOCALIZED_MESSAGES_ENABLED:
        for header in (X_SIMCORE_LANGUAGE, _ACCEPT_LANGUAGE_HEADER):
            if raw := request.headers.get(header):
                request[RQ_LOCALE_KEY] = normalize_locale(raw)
                break
        else:
            request[RQ_LOCALE_KEY] = DEFAULT_LOCALE
    else:
        request[RQ_LOCALE_KEY] = DEFAULT_LOCALE
    return await handler(request)


locale_middleware.__middleware_name__ = (  # type: ignore[attr-defined]
    f"{__name__}.locale_middleware"
)


async def get_user_locale(
    app: web.Application,
    *,
    user_id: UserID,
) -> SupportedLocale:
    """Look up the user's persisted ``users.language`` and return the locale string.

    Falls back to ``DEFAULT_LOCALE`` when no language has been saved.
    Intended for use in background / non-request code (e.g. email dispatch).
    """
    language = await users_service.get_user_language(app, user_id=user_id)
    return language or DEFAULT_LOCALE


async def resolve_effective_locale(
    app: web.Application,
    *,
    user_id: UserID | None,
    locale: SupportedLocale | None,
    group_ids: list[GroupID] | None = None,
) -> SupportedLocale:
    """Resolves the effective locale to render user-facing content in.

    Precedence: explicit ``locale`` argument > DB-stored user language > ``DEFAULT_LOCALE``.
    For multi-recipient sends (``group_ids``) always falls back to ``DEFAULT_LOCALE`` since each
    recipient may have a different language; per-recipient rendering is a future enhancement.
    """
    if locale is not None:
        return locale
    if user_id is not None and not group_ids:
        return await get_user_locale(app, user_id=user_id)
    return DEFAULT_LOCALE
