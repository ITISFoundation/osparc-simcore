# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from functools import cached_property

from pydantic.types import SecretStr
from settings_library.base import BaseCustomSettings
from settings_library.basic_types import PortInt, VersionTag
from settings_library.utils_service import MixinServiceSettings, URLPart


def test_mixing_service_settings_usage(monkeypatch):
    # this test provides an example of usage
    class MySettings(BaseCustomSettings, MixinServiceSettings):
        MY_HOST: str = "example.com"
        MY_PORT: PortInt = 8000
        MY_VTAG: VersionTag | None = None
        MY_SECURE: bool = False

        # optional
        MY_USER: str | None
        MY_PASSWORD: SecretStr | None

        @cached_property
        def api_base_url(self) -> str:
            return self._build_api_base_url(prefix="MY")

        @cached_property
        def origin_url(self) -> str:
            return self._build_origin_url(prefix="MY")

        @cached_property
        def base_url(self) -> str:
            return self._compose_url(
                prefix="MY",
                user=URLPart.OPTIONAL,
                password=URLPart.OPTIONAL,
                port=URLPart.REQUIRED,
            )

    settings = MySettings.create_from_envs()
    assert settings.api_base_url == "http://example.com:8000"
    assert settings.base_url == "http://example.com:8000"
    assert settings.origin_url == "http://example.com"

    # -----------
    monkeypatch.setenv("MY_VTAG", "v9")

    settings = MySettings.create_from_envs()
    assert settings.api_base_url == "http://example.com:8000/v9"
    assert settings.base_url == "http://example.com:8000"
    assert settings.origin_url == "http://example.com"

    # -----------
    monkeypatch.setenv("MY_USER", "me")
    monkeypatch.setenv("MY_PASSWORD", "secret")

    settings = MySettings.create_from_envs()
    assert settings.api_base_url == "http://me:secret@example.com:8000/v9"
    assert settings.base_url == "http://me:secret@example.com:8000"
    assert settings.origin_url == "http://example.com"

    # -----------

    monkeypatch.setenv("MY_SECURE", "1")
    settings = MySettings.create_from_envs()

    assert settings.api_base_url == "https://me:secret@example.com:8000/v9"
    assert settings.base_url == "https://me:secret@example.com:8000"
    assert settings.origin_url == "https://example.com"
