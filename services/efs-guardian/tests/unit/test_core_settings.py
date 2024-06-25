# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict
from simcore_service_efs_guardian.core.settings import ApplicationSettings


def test_settings(app_environment: EnvVarsDict):
    settings = ApplicationSettings.create_from_envs()
    assert settings
