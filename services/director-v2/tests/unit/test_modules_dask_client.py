# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access

import asyncio
from typing import Any, Dict
from uuid import uuid4

import pytest
from _pytest.monkeypatch import MonkeyPatch
from distributed.deploy.spec import SpecCluster
from fastapi.applications import FastAPI
from pytest_mock.plugin import MockerFixture
from simcore_service_director_v2.core.application import init_app
from simcore_service_director_v2.core.errors import ConfigurationError
from simcore_service_director_v2.core.settings import AppSettings
from simcore_service_director_v2.models.schemas.comp_scheduler import TaskIn
from simcore_service_director_v2.modules.dask_client import DaskClient
from starlette.testclient import TestClient


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
def dask_client(
    minimal_dask_config: None,
    dask_spec_local_cluster: SpecCluster,
    minimal_app: FastAPI,
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


@pytest.mark.parametrize("runtime_requirements", ["cpu", "gpu", "mpi", "gpu:mpi"])
async def test_send_computation_task(
    dask_client: DaskClient,
    runtime_requirements: str,
    mocker: MockerFixture,
):
    user_id = 12
    project_id = uuid4()
    node_id = uuid4()
    fake_task = TaskIn(node_id=node_id, runtime_requirements=runtime_requirements)
    mocked_done_callback_fct = mocker.Mock()

    def fake_sidecar_fct(job_id: str, u_id: str, prj_id: str, n_id: str) -> int:
        assert u_id == f"{user_id}"
        assert prj_id == f"{project_id}"
        assert n_id == f"{node_id}"
        return 123

    # start a computation
    dask_client.send_computation_tasks(
        user_id=user_id,
        project_id=project_id,
        single_tasks=[fake_task],
        callback=mocked_done_callback_fct,
        remote_fct=fake_sidecar_fct,
    )

    # we have 1 future in the map now
    assert len(dask_client._taskid_to_future_map) == 1
    # let's get the future
    job_id, future = list(dask_client._taskid_to_future_map.items())[0]
    # this waits for the computation to run
    task_result = future.result(timeout=2)
    # we shall have the results defined above
    assert task_result == 123
    assert future.key == job_id
    mocked_done_callback_fct.assert_called_once()
    mocked_done_callback_fct.reset_mock()

    # start another computation that will be aborted
    dask_client.send_computation_tasks(
        user_id=user_id,
        project_id=project_id,
        single_tasks=[fake_task],
        callback=mocked_done_callback_fct,
        remote_fct=fake_sidecar_fct,
    )

    # we have 2 futures in the map now
    assert len(dask_client._taskid_to_future_map) == 2
    job_id, future = list(dask_client._taskid_to_future_map.items())[1]
    # now let's abort the computation
    assert future.key == job_id
    dask_client.abort_computation_tasks([job_id])
    assert future.cancelled() == True
    await asyncio.sleep(2)
    mocked_done_callback_fct.assert_called_once()
