"""Server-side gettext support helpers — no process-wide install.

Translations are resolved **per-request**: the caller extracts the locale from
each HTTP request (e.g. the ``Accept-Language`` header) and passes it to
:func:`get_translator`.  There is intentionally no app-level default locale;
``gettext.install()`` — which injects ``_()`` into builtins and pins a single
process-wide translator — is never called.

See: https://docs.python.org/3/library/gettext.html

Usage (per-request or per-render):
    from common_library.gettext_support import normalize_locale, get_translator

    translator = get_translator(normalize_locale(accept_language_header))
    translated = translator.gettext(msgid)

Catalogue layout (built by the external extraction pipeline):
    <package_root>/locale/<lang>/LC_MESSAGES/messages.mo

When no .mo file exists for a locale the call returns a NullTranslations object
that passes the English msgid through unchanged — a safe no-op fallback.
"""

import functools
import gettext
import importlib.resources
import logging
import re
from pathlib import Path
from typing import Final, Literal

_logger = logging.getLogger(__name__)

# Extend as new language catalogs are added. See test_supported_locale_catalog_alignment.
type SupportedLocale = Literal["en", "es_ES", "zh_CN"]
DEFAULT_LOCALE: Final[SupportedLocale] = "en"


_DOMAIN: Final[str] = "messages"
_LOCALE_DIR: Final[str] = str(importlib.resources.files("common_library") / "locale")
assert Path(_LOCALE_DIR).is_dir(), f"locale directory not found: {_LOCALE_DIR}"  # nosec


# Accept-Language tag normalisation: "es-ES" -> "es_ES", "zh-hans" -> "zh_hans"
_ACCEPT_LANG_RE: re.Pattern[str] = re.compile(r"^(?P<lang>[a-zA-Z]{2,3})(?:[_-](?P<region>[a-zA-Z]{2,8}))?")


def normalize_locale(raw: str) -> str:
    """Normalise an Accept-Language tag or HTTP header value to a gettext locale string.

    Examples:
        "es-ES"              -> "es_ES"
        "zh-CN,zh;q=0.9"    -> "zh_CN"
        "en"                 -> "en"
        "  ES_es ; q=0.8"   -> "es_ES"
    """
    # Take the first tag, stopping at the first comma or semicolon
    first_tag = re.split(r"[,;]", raw, maxsplit=1)[0].strip()
    m = _ACCEPT_LANG_RE.match(first_tag)
    if not m:
        return DEFAULT_LOCALE
    lang = m.group("lang").lower()
    region = m.group("region")
    normalized = f"{lang}_{region.upper()}" if region else lang

    if normalized.startswith("en_"):
        return DEFAULT_LOCALE
    # Frontend emits bare "zh" due to qooxdoo constraints; backend catalogs are zh_CN.
    if normalized == "zh":
        return "zh_CN"
    return normalized


@functools.cache
def _load(locale: str) -> gettext.NullTranslations:
    """Load a GNUTranslations for *locale*, or NullTranslations if no .mo found."""
    try:
        return gettext.translation(
            _DOMAIN,
            localedir=_LOCALE_DIR,
            languages=[locale],
        )
    except FileNotFoundError:
        _logger.warning("No catalog for locale %r (domain=%r); using EN pass-through", locale, _DOMAIN)
        return gettext.NullTranslations()


def get_translator(locale: str) -> gettext.NullTranslations:
    """Return a cached translator for *locale*.

    Exposes ``gettext(msgid)`` and ``ngettext(singular, plural, n)``.
    """
    return _load(locale)


def setup_translations(supported_locales: list[str]) -> None:
    """Pre-warm the translator cache for every supported locale at startup.

    Call once during application initialisation so the first request for each
    locale does not incur an I/O hit.
    """
    for locale in supported_locales:
        get_translator(locale)
