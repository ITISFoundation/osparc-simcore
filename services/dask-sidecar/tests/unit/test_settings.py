# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from pytest import MonkeyPatch
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_service_dask_sidecar.settings import Settings


def test_settings_as_worker(app_environment: EnvVarsDict, monkeypatch: MonkeyPatch):
    settings = Settings.create_from_envs()
    assert settings.as_worker()


def test_settings_as_scheduler(app_environment: EnvVarsDict, monkeypatch: MonkeyPatch):
    assert app_environment.get("DASK_START_AS_SCHEDULER", None) != "1"
    monkeypatch.setenv("DASK_START_AS_SCHEDULER", "1")

    settings = Settings.create_from_envs()
    assert settings.as_scheduler()
