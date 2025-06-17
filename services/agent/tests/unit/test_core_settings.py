# pylint: disable=unused-variable
# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name


from pytest_simcore.helpers.monkeypatch_envs import (
    EnvVarsDict,
)
from simcore_service_agent.core.settings import ApplicationSettings


def test_valid_application_settings(service_env: EnvVarsDict):
    assert service_env

    settings = ApplicationSettings()  # type: ignore
    assert settings

    assert settings == ApplicationSettings.create_from_envs()
