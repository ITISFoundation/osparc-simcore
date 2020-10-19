# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
import logging

import pytest

from simcore_service_director_v2.core.settings import (
    AppSettings,
    BootModeEnum,
    RegistrySettings,
)


def test_loading_env_devel_in_settings(project_env_devel_environment):

    # loads from environ
    settings = AppSettings.create_from_env()
    print("captured settings: \n", settings.json(indent=2))

    assert settings.boot_mode == BootModeEnum.DEBUG
    assert settings.loglevel == logging.DEBUG

    assert settings.postgres.dsn == "postgresql://test:test@localhost:5432/test"


def test_create_registry_settings(project_env_devel_environment, monkeypatch):
    monkeypatch.setenv("REGISTRY_URL", "http://registry:5000")
    monkeypatch.setenv("REGISTRY_AUTH", "True")
    monkeypatch.setenv("REGISTRY_USER", "admin")
    monkeypatch.setenv("REGISTRY_PW", "adminadmin")
    monkeypatch.setenv("REGISTRY_SSL", "1")

    settings = RegistrySettings()

    # http -> https
    assert settings.api_url == "https://registry:5000/v2"


def test_registry_settings_error(project_env_devel_environment, monkeypatch):
    monkeypatch.setenv("REGISTRY_URL", "http://registry:5000")
    monkeypatch.setenv("REGISTRY_AUTH", "True")
    monkeypatch.setenv("REGISTRY_USER", "")
    monkeypatch.setenv("REGISTRY_PW", "")
    monkeypatch.setenv("REGISTRY_SSL", "False")

    with pytest.raises(ValueError, match="Authentication REQUIRES a secured channel"):
        RegistrySettings()
