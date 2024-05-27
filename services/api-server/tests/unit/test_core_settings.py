# pylint: disable=unused-variable
# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name

import logging

import pytest
from pytest_simcore.helpers.utils_envs import (
    EnvVarsDict,
    delenvs_from_dict,
    setenvs_from_dict,
)
from simcore_service_api_server.core.settings import ApplicationSettings, BootModeEnum


def app_environment(
    monkeypatch: pytest.MonkeyPatch,
    app_environment: EnvVarsDict,
    external_envfile_dict: EnvVarsDict,
) -> EnvVarsDict:
    """
    NOTE: To run against repo.config in osparc-config repo

    ln -s /path/to/osparc-config/deployments/mydeploy.com/repo.config .secrets
    pytest --external-envfile=.secrets tests/unit/test_core_settings.py

    """
    if external_envfile_dict:
        delenvs_from_dict(monkeypatch, app_environment, raising=False)
        return setenvs_from_dict(
            monkeypatch,
            {**external_envfile_dict},
        )
    return app_environment


def test_unit_app_environment(app_environment: EnvVarsDict):
    assert app_environment

    settings = ApplicationSettings.create_from_envs()
    print("captured settings: \n", settings.json(indent=2))

    assert settings.SC_BOOT_MODE == BootModeEnum.PRODUCTION
    assert settings.log_level == logging.DEBUG

    assert settings.API_SERVER_POSTGRES is None
