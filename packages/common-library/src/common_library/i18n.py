"""Server-side i18n helpers (gettext-based, no global install).

Usage (per-request or per-render):
    from common_library.i18n import get_translator

    translator = get_translator(locale)
    translated = translator.gettext(msgid)

Catalogue layout (built by the external extraction pipeline):
    <package_root>/locale/<lang>/LC_MESSAGES/messages.mo

When no .mo file exists for a locale the call returns a NullTranslations object
that passes the English msgid through unchanged — i.e. a safe no-op fallback.
"""

import gettext
import logging
import re
from pathlib import Path
from typing import Final, Literal

_logger = logging.getLogger(__name__)

DEFAULT_LOCALE: Final[str] = "en"

# Locales with compiled .mo catalogues shipped in this package.
# Extend this tuple as new languages are added to the extraction pipeline.
type SupportedLocale = Literal["en", "es_ES", "zh_CN"]
_DOMAIN: Final[str] = "messages"
_LOCALE_DIR: Final[Path] = Path(__file__).parent / "locale"

# Module-level cache: locale string → loaded translator.
# Access is single-threaded (asyncio event loop), so a plain dict is safe.
_cache: dict[str, gettext.NullTranslations] = {}

# Accept-Language tag normalisation: "es-ES" → "es_ES", "zh-hans" → "zh_hans"
_ACCEPT_LANG_RE: re.Pattern[str] = re.compile(r"^([a-zA-Z]{2,3})(?:[_-]([a-zA-Z]{2,8}))?")


def normalize_locale(raw: str) -> str:
    """Normalise an Accept-Language tag or HTTP header value to a gettext locale string.

    Examples:
        "es-ES"              → "es_ES"
        "zh-CN,zh;q=0.9"    → "zh_CN"
        "en"                 → "en"
        "  ES_es ; q=0.8"   → "es_ES"
    """
    # Take the first tag, stopping at the first comma or semicolon
    first_tag = re.split(r"[,;]", raw, maxsplit=1)[0].strip()
    m = _ACCEPT_LANG_RE.match(first_tag)
    if not m:
        return DEFAULT_LOCALE
    lang = m.group(1).lower()
    region = m.group(2)
    if region:
        return f"{lang}_{region.upper()}"
    return lang


def _load(locale: str) -> gettext.NullTranslations:
    """Load a GNUTranslations for *locale*, or NullTranslations if no .mo found."""
    try:
        return gettext.translation(
            _DOMAIN,
            localedir=str(_LOCALE_DIR),
            languages=[locale],
        )
    except FileNotFoundError:
        _logger.debug("No catalogue for locale %r (domain=%r); using EN pass-through", locale, _DOMAIN)
        return gettext.NullTranslations()


def get_translator(locale: str) -> gettext.NullTranslations:
    """Return a cached translator for *locale*.

    Thread-safety: relies on the asyncio event loop's single-threaded execution.
    The returned object exposes the standard ``gettext(msgid)`` and
    ``ngettext(singular, plural, n)`` methods.
    """
    if locale not in _cache:
        _cache[locale] = _load(locale)
    return _cache[locale]


def setup_translations(supported_locales: list[str]) -> None:
    """Pre-warm the translator cache for every supported locale at startup.

    Call once during application initialisation so the first request for each
    locale does not incur an I/O hit.
    """
    for locale in supported_locales:
        get_translator(locale)
