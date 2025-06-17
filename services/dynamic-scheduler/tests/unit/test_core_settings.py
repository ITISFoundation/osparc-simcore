# pylint: disable=unused-variable
# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name
"""
We validate actual envfiles (e.g. repo.config files) by passing them via the CLI

$ ln -s /path/to/osparc-config/deployments/mydeploy.com/repo.config .secrets
$ pytest --external-envfile=.secrets --pdb tests/unit/test_core_settings.py

"""


import pytest
from pytest_simcore.helpers.monkeypatch_envs import (
    EnvVarsDict,
    delenvs_from_dict,
    setenvs_from_dict,
)
from simcore_service_dynamic_scheduler.core.settings import ApplicationSettings


@pytest.fixture
def app_environment(
    monkeypatch: pytest.MonkeyPatch,
    app_environment: EnvVarsDict,
    external_envfile_dict: EnvVarsDict,
) -> EnvVarsDict:
    """OVERRIDES app_environment fixture:

    Enables using external envfiles (e.g. repo.config files) to run tests against
    within this test module.
    """
    if external_envfile_dict:
        delenvs_from_dict(monkeypatch, app_environment, raising=False)
        return setenvs_from_dict(
            monkeypatch,
            {**external_envfile_dict},
        )
    return app_environment


def test_valid_application_settings(app_environment: EnvVarsDict):
    assert app_environment

    settings = ApplicationSettings()  # type: ignore
    assert settings
    assert settings == ApplicationSettings.create_from_envs()
