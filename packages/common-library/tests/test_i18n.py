"""Tests for common_library.i18n"""

import gettext
from pathlib import Path
from typing import Final

import polib
import pytest
from common_library.i18n import (
    _LOCALE_DIR,
    DEFAULT_LOCALE,
    get_translator,
    normalize_locale,
    setup_translations,
)

# Locales that have a compiled .po catalog (excludes "en": prose-as-key, no catalog needed)
_TRANSLATED_LOCALES: Final = ["es_ES", "zh_CN"]


@pytest.mark.parametrize("locale", _TRANSLATED_LOCALES)
def test_locale_directory_exists(locale: str) -> None:
    assert (Path(_LOCALE_DIR) / locale / "LC_MESSAGES").is_dir()


@pytest.mark.parametrize("locale", _TRANSLATED_LOCALES)
def test_compiled_mo_exists(locale: str) -> None:
    """Assert the .mo file is present alongside the .po (compiled at install/build time)."""
    mo_path = Path(_LOCALE_DIR) / locale / "LC_MESSAGES" / "messages.mo"
    assert mo_path.exists(), (
        f"Compiled .mo not found at {mo_path}. "
        "Run 'make install-dev' (dev) or reinstall the package (non-editable) to compile it."
    )


@pytest.mark.parametrize("locale", ["en", "es_ES", "zh_CN", "unknown"])
def test_get_translator_returns_pass_through(locale: str) -> None:
    translator = get_translator(locale)
    assert translator.gettext("hello") == "hello"


def test_get_translator_is_cached() -> None:
    assert get_translator("en") is get_translator("en")


def test_default_locale() -> None:
    assert DEFAULT_LOCALE == "en"


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("es-ES", "es_ES"),  # region present → lang_REGION
        ("zh-CN,zh;q=0.9", "zh_CN"),  # Accept-Language header, picks first tag
        ("en", "en"),  # no region
        ("  ES_es ; q=0.8", "es_ES"),  # leading whitespace + mixed case
        ("123-invalid", "en"),  # starts with digits → no regex match → DEFAULT_LOCALE
    ],
)
def test_normalize_locale(raw: str, expected: str) -> None:
    assert normalize_locale(raw) == expected


def test_setup_translations_prewarms_cache() -> None:
    setup_translations(["es_ES", "zh_CN"])
    # After pre-warming, get_translator must return a cached (non-None) object
    assert get_translator("es_ES") is get_translator("es_ES")
    assert get_translator("zh_CN") is get_translator("zh_CN")


@pytest.mark.parametrize("locale", _TRANSLATED_LOCALES)
def test_translation_catalog_loads_and_translates(locale: str, tmp_path: Path) -> None:
    """Verify the .po catalog compiles, loads, and produces actual translations.

    Tests that translation *happens* — not the specific translated value.
    Robust against any change to the translated strings.
    """
    po_path = Path(_LOCALE_DIR) / locale / "LC_MESSAGES" / "messages.po"
    assert po_path.exists(), f".po not found: {po_path}"

    mo_dir = tmp_path / locale / "LC_MESSAGES"
    mo_dir.mkdir(parents=True)
    polib.pofile(str(po_path)).save_as_mofile(str(mo_dir / "messages.mo"))

    t = gettext.translation("messages", localedir=str(tmp_path), languages=[locale])

    # Pick the first translated entry from the .po and confirm gettext returns its msgstr
    translated = polib.pofile(str(po_path)).translated_entries()
    assert translated, f"No translated entries in .po for {locale}"
    first = translated[0]
    assert t.gettext(first.msgid) == first.msgstr
