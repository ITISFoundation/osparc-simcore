# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from functools import cached_property

import pytest
from pydantic import AnyHttpUrl, TypeAdapter
from pydantic.types import SecretStr
from settings_library.base import BaseCustomSettings
from settings_library.basic_types import PortInt, VersionTag
from settings_library.catalog import CatalogSettings
from settings_library.director_v2 import DirectorV2Settings
from settings_library.storage import StorageSettings
from settings_library.utils_service import MixinServiceSettings, URLPart
from settings_library.webserver import WebServerSettings


def test_mixing_service_settings_usage(monkeypatch: pytest.MonkeyPatch):
    # this test provides an example of usage
    class MySettings(BaseCustomSettings, MixinServiceSettings):
        MY_HOST: str = "example.com"
        MY_PORT: PortInt = 8000
        MY_VTAG: VersionTag | None = None
        MY_SECURE: bool = False

        # optional (in Pydantic v2 requires a default)
        MY_USER: str | None = None
        MY_PASSWORD: SecretStr | None = None

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


@pytest.mark.parametrize(
    "service_settings_cls",
    [WebServerSettings, CatalogSettings, DirectorV2Settings, StorageSettings],
)
def test_service_settings_base_urls(service_settings_cls: type):

    assert issubclass(service_settings_cls, BaseCustomSettings)
    assert issubclass(service_settings_cls, MixinServiceSettings)

    settings_with_defaults = service_settings_cls()

    base_url = TypeAdapter(AnyHttpUrl).validate_python(settings_with_defaults.base_url)
    api_base_url = TypeAdapter(AnyHttpUrl).validate_python(settings_with_defaults.api_base_url)

    assert base_url.path != api_base_url.path
    assert (base_url.scheme, base_url.host, base_url.port) == (
        api_base_url.scheme,
        api_base_url.host,
        api_base_url.port,
    )
