# pylint: disable=unused-variable
# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name


import pytest
from pytest_simcore.helpers.monkeypatch_envs import (
    EnvVarsDict,
    delenvs_from_dict,
    setenvs_from_dict,
)
from simcore_service_api_server.core.settings import ApplicationSettings


@pytest.fixture
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


def test_valid_application_settings(app_environment: EnvVarsDict):
    """
    We can validate actual .env files (also refered as `repo.config` files) by passing them via the CLI

    $ ln -s /path/to/osparc-config/deployments/mydeploy.com/repo.config .secrets
    $ pytest --external-envfile=.secrets --pdb tests/unit/test_core_settings.py

    """
    assert app_environment

    settings = ApplicationSettings()  # type: ignore
    assert settings

    assert settings == ApplicationSettings.create_from_envs()
