# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access

from typing import Any, Dict
from uuid import uuid4

import pytest
from _pytest.monkeypatch import MonkeyPatch
from dask.distributed import LocalCluster
from fastapi.applications import FastAPI
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from simcore_service_director_v2.core.application import init_app
from simcore_service_director_v2.core.errors import ConfigurationError
from simcore_service_director_v2.core.settings import AppSettings
from simcore_service_director_v2.models.domains.comp_tasks import Image
from simcore_service_director_v2.modules.dask_client import DaskClient, DaskTaskIn
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


def test_dask_client_missing_raises_configuration_error(
    mock_env: None, minimal_dask_config: None, monkeypatch: MonkeyPatch
):
    monkeypatch.setenv("DIRECTOR_V2_DASK_CLIENT_ENABLED", "0")
    settings = AppSettings.create_from_envs()
    app = init_app(settings)

    with TestClient(app, raise_server_exceptions=True) as client:
        with pytest.raises(ConfigurationError):
            DaskClient.instance(client.app)


@pytest.fixture
def mocked_dask_cluster(monkeypatch: MonkeyPatch) -> LocalCluster:
    cluster = LocalCluster(n_workers=2, threads_per_worker=1)
    scheduler_address = URL(cluster.scheduler_address)
    monkeypatch.setenv("DASK_SCHEDULER_HOST", scheduler_address.host or "invalid")
    monkeypatch.setenv("DASK_SCHEDULER_PORT", f"{scheduler_address.port}")
    yield cluster
    cluster.close()


@pytest.fixture
def dask_client(
    minimal_dask_config: None, mocked_dask_cluster: LocalCluster, minimal_app: FastAPI
) -> DaskClient:
    client = DaskClient.instance(minimal_app)
    assert client
    yield client


def test_dask_client_is_created(dask_client: DaskClient):
    pass


def test_local_dask_cluster_through_client(dask_client: DaskClient):
    def test_fct_add(x: int, y: int) -> int:
        return x + y

    future = dask_client.client.submit(test_fct_add, 2, 5)
    assert future
    result = future.result(timeout=2)
    assert result == 7


def test_send_computation_task(dask_client: DaskClient):
    job_id = "a_fake_job_id"
    user_id = 12
    project_id = ProjectID(uuid4())
    node_id = NodeID(uuid4())
    pass


@pytest.mark.parametrize(
    "image, exp_requirements_str",
    [
        (
            Image(
                name="simcore/services/comp/itis/sleeper",
                tag="1.0.0",
                requires_gpu=False,
                requires_mpi=False,
            ),
            "cpu",
        ),
        (
            Image(
                name="simcore/services/comp/itis/sleeper",
                tag="1.0.0",
                requires_gpu=True,
                requires_mpi=False,
            ),
            "gpu",
        ),
        (
            Image(
                name="simcore/services/comp/itis/sleeper",
                tag="1.0.0",
                requires_gpu=False,
                requires_mpi=True,
            ),
            "mpi",
        ),
        (
            Image(
                name="simcore/services/comp/itis/sleeper",
                tag="1.0.0",
                requires_gpu=True,
                requires_mpi=True,
            ),
            "gpu:mpi",
        ),
    ],
)
def test_dask_task_in_model(image: Image, exp_requirements_str: str):
    node_id = uuid4()
    dask_task = DaskTaskIn.from_node_image(node_id, image)
    assert dask_task
    assert dask_task.node_id == node_id
    assert dask_task.runtime_requirements == exp_requirements_str
