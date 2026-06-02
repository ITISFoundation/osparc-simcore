# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import pytest
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_service_catalog._constants import DEFAULT_DIRECTOR_BULK_FETCH_LEASE
from simcore_service_catalog.core.settings import ApplicationSettings


def test_valid_application_settings(app_environment: EnvVarsDict):
    assert app_environment

    settings = ApplicationSettings()  # type: ignore
    assert settings

    assert settings == ApplicationSettings.create_from_envs()


def test_director_bulk_fetch_lease_defaults(app_environment: EnvVarsDict):
    settings = ApplicationSettings.create_from_envs()
    assert settings.CATALOG_DIRECTOR_BULK_FETCH_LEASE == DEFAULT_DIRECTOR_BULK_FETCH_LEASE


def test_director_bulk_fetch_lease_is_configurable(monkeypatch: pytest.MonkeyPatch, app_environment: EnvVarsDict):
    setenvs_from_dict(monkeypatch, {"CATALOG_DIRECTOR_BULK_FETCH_LEASE": "90"})

    settings = ApplicationSettings.create_from_envs()
    assert settings.CATALOG_DIRECTOR_BULK_FETCH_LEASE == 90
