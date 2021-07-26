# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import pytest
from simcore_service_dask_sidecar.settings import Settings


@pytest.fixture
def mock_service_envs(mock_env_devel_environment, monkeypatch):

    # Variables directly define inside Dockerfile
    monkeypatch.setenv("SC_BOOT_MODE", "debug-ptvsd")

    # Variables  passed upon start via services/docker-compose.yml file under dask-sidecar/scheduler
    monkeypatch.setenv("DASK_START_AS_SCHEDULER", "1")

    monkeypatch.setenv("SWARM_STACK_NAME", "simcore")
    monkeypatch.setenv("SIDECAR_LOGLEVEL", "WARNING")
    monkeypatch.setenv("SIDECAR_HOST_HOSTNAME_PATH", "/home/scu/hostname")
    monkeypatch.setenv("START_AS_MODE_CPU", "0")


def test_settings(mock_service_envs, monkeypatch):

    monkeypatch.delenv("DASK_START_AS_SCHEDULER")
    settings = Settings.create_from_envs()
    assert settings.as_worker()

    monkeypatch.setenv("DASK_START_AS_SCHEDULER", "1")
    settings = Settings.create_from_envs()
    assert settings.as_scheduler()
