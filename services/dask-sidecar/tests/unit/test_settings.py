# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from typing import Dict, Optional

import pytest
from _pytest.monkeypatch import MonkeyPatch
from simcore_service_dask_sidecar.settings import Settings


@pytest.fixture
def mock_service_envs(
    mock_env_devel_environment: Dict[str, Optional[str]], monkeypatch: MonkeyPatch
) -> None:

    # Variables directly define inside Dockerfile
    monkeypatch.setenv("SC_BOOT_MODE", "debug-ptvsd")

    # Variables  passed upon start via services/docker-compose.yml file under dask-sidecar/scheduler
    monkeypatch.setenv("DASK_START_AS_SCHEDULER", "1")

    monkeypatch.setenv("SWARM_STACK_NAME", "simcore")
    monkeypatch.setenv("SIDECAR_LOGLEVEL", "DEBUG")
    monkeypatch.setenv(
        "SIDECAR_COMP_SERVICES_SHARED_VOLUME_NAME", "simcore_computational_shared_data"
    )
    monkeypatch.setenv(
        "SIDECAR_COMP_SERVICES_SHARED_FOLDER", "/home/scu/computational_shared_data"
    )


def test_settings(mock_service_envs: None, monkeypatch: MonkeyPatch):

    monkeypatch.delenv("DASK_START_AS_SCHEDULER")
    settings = Settings.create_from_envs()
    assert settings.as_worker()

    monkeypatch.setenv("DASK_START_AS_SCHEDULER", "1")
    settings = Settings.create_from_envs()
    assert settings.as_scheduler()
