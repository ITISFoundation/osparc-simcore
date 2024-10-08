from datetime import timedelta

import pytest
from common_library.pydantic_settings_validators import (
    validate_timedelta_in_legacy_mode,
)
from faker import Faker
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict


def test_validate_timedelta_in_legacy_mode(
    monkeypatch: pytest.MonkeyPatch, faker: Faker
):
    class Settings(BaseSettings):
        APP_NAME: str
        REQUEST_TIMEOUT: timedelta = Field(default=timedelta(seconds=40))

        _legacy_parsing_request_timeout = validate_timedelta_in_legacy_mode(
            "REQUEST_TIMEOUT"
        )

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
