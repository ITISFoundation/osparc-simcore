"""Tests for common_library.i18n"""

import pytest
from common_library.i18n import _LOCALE_DIR, DEFAULT_LOCALE, get_translator


@pytest.mark.parametrize("locale", ["en", "es_ES", "zh_CN"])
def test_locale_directory_exists(locale: str) -> None:
    assert (_LOCALE_DIR / locale / "LC_MESSAGES").is_dir()


@pytest.mark.parametrize("locale", ["en", "es_ES", "zh_CN", "unknown"])
def test_get_translator_returns_pass_through(locale: str) -> None:
    translator = get_translator(locale)
    assert translator.gettext("hello") == "hello"


def test_get_translator_is_cached() -> None:
    assert get_translator("en") is get_translator("en")


def test_default_locale() -> None:
    assert DEFAULT_LOCALE == "en"
