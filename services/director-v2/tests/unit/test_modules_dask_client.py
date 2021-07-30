# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access

from typing import Any, Dict

import pytest
from _pytest.monkeypatch import MonkeyPatch
from dask.distributed import LocalCluster
from fastapi.applications import FastAPI
from simcore_service_director_v2.core.application import init_app
from simcore_service_director_v2.core.errors import ConfigurationError
from simcore_service_director_v2.core.settings import AppSettings
from simcore_service_director_v2.modules.dask_client import DaskClient
from starlette.testclient import TestClient
from yarl import URL


@pytest.fixture
def minimal_dask_config(
    project_env_devel_environment: Dict[str, Any], monkeypatch: MonkeyPatch
) -> None:
    """set a minimal configuration for testing the dask connection only"""
    monkeypatch.setenv("DIRECTOR_ENABLED", "0")
    monkeypatch.setenv("POSTGRES_ENABLED", "0")
    monkeypatch.setenv("CELERY_ENABLED", "0")
    monkeypatch.setenv("REGISTRY_ENABLED", "0")
    monkeypatch.setenv("DIRECTOR_V2_DYNAMIC_SIDECAR_ENABLED", "false")
    monkeypatch.setenv("DIRECTOR_V0_ENABLED", "0")
    monkeypatch.setenv("DIRECTOR_V2_POSTGRES_ENABLED", "0")
    monkeypatch.setenv("DIRECTOR_V2_CELERY_ENABLED", "0")
    monkeypatch.setenv("DIRECTOR_V2_CELERY_SCHEDULER_ENABLED", "0")
    monkeypatch.setenv("DIRECTOR_V2_DASK_CLIENT_ENABLED", "1")
    monkeypatch.setenv("DIRECTOR_V2_DASK_SCHEDULER_ENABLED", "0")


@pytest.fixture
def mocked_dask_cluster(monkeypatch: MonkeyPatch) -> LocalCluster:
    cluster = LocalCluster(n_workers=2, threads_per_worker=1)
    scheduler_address = URL(cluster.scheduler_address)
    monkeypatch.setenv("DASK_SCHEDULER_HOST", scheduler_address.host)
    monkeypatch.setenv("DASK_SCHEDULER_PORT", scheduler_address.port)
    return cluster


def test_dask_client_missing_raises_configuration_error(
    mock_env: None, minimal_dask_config: None, monkeypatch: MonkeyPatch
):
    monkeypatch.setenv("DIRECTOR_V2_DASK_CLIENT_ENABLED", "0")
    settings = AppSettings.create_from_envs()
    app = init_app(settings)

    with TestClient(app, raise_server_exceptions=True) as client:
        with pytest.raises(ConfigurationError):
            DaskClient.instance(client.app)


def test_dask_client_creation(
    minimal_dask_config: None, mocked_dask_cluster: LocalCluster, minimal_app: FastAPI
):
    client = DaskClient.instance(minimal_app)
    assert client
