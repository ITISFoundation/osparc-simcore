from datetime import timedelta
from typing import Annotated

import pytest
from common_library.pydantic_validators import (
    _validate_legacy_timedelta_str,
    to_secret_str,
    validate_numeric_string_as_timedelta,
)
from faker import Faker
from pydantic import BeforeValidator, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict


def test_validate_legacy_timedelta(monkeypatch: pytest.MonkeyPatch, faker: Faker):
    class Settings(BaseSettings):
        APP_NAME: str
        REQUEST_TIMEOUT: Annotated[timedelta, BeforeValidator(_validate_legacy_timedelta_str)] = timedelta(hours=1)

        model_config = SettingsConfigDict()

    app_name = faker.pystr()
    env_vars: dict[str, str | bool] = {"APP_NAME": app_name}

    # without timedelta
    setenvs_from_dict(monkeypatch, env_vars)
    settings = Settings()
    print(settings.model_dump())
    assert app_name == settings.APP_NAME
    assert timedelta(hours=1) == settings.REQUEST_TIMEOUT

    # with timedelta in seconds
    env_vars["REQUEST_TIMEOUT"] = "2 1:10:00"
    setenvs_from_dict(monkeypatch, env_vars)
    settings = Settings()
    print(settings.model_dump())
    assert app_name == settings.APP_NAME
    assert timedelta(days=2, hours=1, minutes=10) == settings.REQUEST_TIMEOUT


def test_validate_timedelta_in_legacy_mode(monkeypatch: pytest.MonkeyPatch, faker: Faker):
    class Settings(BaseSettings):
        APP_NAME: str
        REQUEST_TIMEOUT: timedelta = timedelta(seconds=40)

        _validate_request_timeout = validate_numeric_string_as_timedelta("REQUEST_TIMEOUT")

        model_config = SettingsConfigDict()

    app_name = faker.pystr()
    env_vars: dict[str, str | bool] = {"APP_NAME": app_name}

    # without timedelta
    setenvs_from_dict(monkeypatch, env_vars)
    settings = Settings()
    print(settings.model_dump())
    assert app_name == settings.APP_NAME
    assert timedelta(seconds=40) == settings.REQUEST_TIMEOUT

    # with timedelta in seconds
    env_vars["REQUEST_TIMEOUT"] = "5555"
    setenvs_from_dict(monkeypatch, env_vars)
    settings = Settings()
    print(settings.model_dump())
    assert app_name == settings.APP_NAME
    assert timedelta(seconds=5555) == settings.REQUEST_TIMEOUT


@pytest.mark.parametrize(
    "value,expected",
    [
        pytest.param("s3cr3t", SecretStr("s3cr3t"), id="str-wrapped"),
        pytest.param(123, 123, id="int-passthrough"),
        pytest.param(None, None, id="none-passthrough"),
    ],
)
def test_to_secret_str(value: object, expected: object):
    assert to_secret_str(value) == expected
