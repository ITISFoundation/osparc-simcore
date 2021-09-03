# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access

import asyncio
import random
from typing import Any, Dict
from uuid import uuid4

import pytest
from _pytest.monkeypatch import MonkeyPatch
from distributed.deploy.spec import SpecCluster
from distributed.worker import TaskState
from fastapi.applications import FastAPI
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from pytest_mock.plugin import MockerFixture
from simcore_service_director_v2.core.application import init_app
from simcore_service_director_v2.core.errors import ConfigurationError
from simcore_service_director_v2.core.settings import AppSettings
from simcore_service_director_v2.models.domains.comp_tasks import Image
from simcore_service_director_v2.models.schemas.constants import ClusterID, UserID
from simcore_service_director_v2.models.schemas.services import NodeRequirements
from simcore_service_director_v2.modules.dask_client import (
    CLUSTER_RESOURCE_MOCK_USAGE,
    DaskClient,
)
from starlette.testclient import TestClient
from tenacity import retry, retry_if_exception_type, stop_after_delay, wait_random


@retry(
    stop=stop_after_delay(10),
    wait=wait_random(0, 1),
    retry=retry_if_exception_type(AssertionError),
    reraise=True,
)
async def _wait_for_call(mocked_fct):
    mocked_fct.assert_called_once()


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


@pytest.fixture
def project_id() -> ProjectID:
    return uuid4()


@pytest.fixture
def node_id() -> NodeID:
    return uuid4()


@pytest.mark.parametrize(
    "image, expected_annotations",
    [
        (
            Image(
                name="simcore/services/comp/pytest",
                tag="1.4.5",
                node_requirements=NodeRequirements(CPU=1, RAM="128 MiB"),
            ),
            {"resources": {"CPU": 1.0, "RAM": 128 * 1024 * 1024}},
        ),
        (
            Image(
                name="simcore/services/comp/pytest",
                tag="1.4.5",
                node_requirements=NodeRequirements(CPU=1, GPU=1, RAM="256 MiB"),
            ),
            {
                "resources": {"CPU": 1.0, "GPU": 1.0, "RAM": 256 * 1024 * 1024},
            },
        ),
        (
            Image(
                name="simcore/services/comp/pytest",
                tag="1.4.5",
                node_requirements=NodeRequirements(CPU=2, RAM="128 MiB", MPI=1),
            ),
            {
                "resources": {"CPU": 2.0, "MPI": 1.0, "RAM": 128 * 1024 * 1024},
            },
        ),
    ],
)
async def test_send_computation_task(
    dask_client: DaskClient,
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
    cluster_id: ClusterID,
    cluster_id_resource: str,
    image: Image,
    expected_annotations: Dict[str, Any],
    mocker: MockerFixture,
):
    # INIT
    expected_annotations["resources"].update(
        {cluster_id_resource: CLUSTER_RESOURCE_MOCK_USAGE}
    )
    fake_task = {node_id: image}
    mocked_done_callback_fct = mocker.Mock()

    # NOTE: We pass another fct so it can run in our localy created dask cluster
    def fake_sidecar_fct(job_id: str, u_id: str, prj_id: str, n_id: str) -> int:
        from dask.distributed import get_worker

        worker = get_worker()
        task: TaskState = worker.tasks.get(worker.get_current_task())
        assert task is not None
        assert task.annotations == expected_annotations
        assert u_id == user_id
        assert prj_id == project_id
        assert n_id == node_id
        return 123

    # TEST COMPUTATION RUNS THROUGH
    dask_client.send_computation_tasks(
        user_id=user_id,
        project_id=project_id,
        cluster_id=cluster_id,
        tasks=fake_task,
        callback=mocked_done_callback_fct,
        remote_fct=fake_sidecar_fct,
    )
    assert (
        len(dask_client._taskid_to_future_map) == 1
    ), "dask client did not store the future of the task sent"

    job_id, future = list(dask_client._taskid_to_future_map.items())[0]
    # this waits for the computation to run
    task_result = future.result(timeout=2)
    assert task_result == 123
    assert future.key == job_id
    await _wait_for_call(mocked_done_callback_fct)
    mocked_done_callback_fct.assert_called_once()
    mocked_done_callback_fct.reset_mock()
    assert (
        len(dask_client._taskid_to_future_map) == 0
    ), "the list of futures was not cleaned correctly"

    # TEST COMPUTATION ABORTION
    dask_client.send_computation_tasks(
        user_id=user_id,
        project_id=project_id,
        cluster_id=cluster_id,
        tasks=fake_task,
        callback=mocked_done_callback_fct,
        remote_fct=fake_sidecar_fct,
    )
    assert (
        len(dask_client._taskid_to_future_map) == 1
    ), "dask client did not store the future of the task sent"

    job_id, future = list(dask_client._taskid_to_future_map.items())[0]
    # now let's abort the computation
    assert future.key == job_id
    dask_client.abort_computation_tasks([job_id])
    assert future.cancelled() == True
    await _wait_for_call(mocked_done_callback_fct)
    mocked_done_callback_fct.assert_called_once()
    mocked_done_callback_fct.reset_mock()
    assert (
        len(dask_client._taskid_to_future_map) == 0
    ), "the list of futures was not cleaned correctly"

    # TEST RUNNING COMPUTATION IN NON-EXISTING CLUSTER SHOULD TIMEOUT
    dask_client.send_computation_tasks(
        user_id=user_id,
        project_id=project_id,
        cluster_id=random.randint(cluster_id + 1, 100),
        tasks=fake_task,
        callback=mocked_done_callback_fct,
        remote_fct=fake_sidecar_fct,
    )
    assert (
        len(dask_client._taskid_to_future_map) == 1
    ), "dask client did not store the future of the task sent"
    job_id, future = list(dask_client._taskid_to_future_map.items())[0]

    with pytest.raises(asyncio.TimeoutError):
        future.result(timeout=2)
    dask_client.abort_computation_tasks([job_id])
    assert future.cancelled() == True
    await _wait_for_call(mocked_done_callback_fct)
    mocked_done_callback_fct.assert_called_once()
    mocked_done_callback_fct.reset_mock()
    assert (
        len(dask_client._taskid_to_future_map) == 0
    ), "the list of futures was not cleaned correctly"


@pytest.mark.parametrize(
    "req_example", NodeRequirements.Config.schema_extra["examples"]
)
def test_node_requirements_correctly_convert_to_dask_resources(
    req_example: Dict[str, Any]
):
    node_reqs = NodeRequirements(**req_example)
    assert node_reqs
    dask_resources = node_reqs.dict(exclude_unset=True, by_alias=True)
    # all the dask resources shall be of type: RESOURCE_NAME: VALUE
    for resource_key, resource_value in dask_resources.items():
        assert isinstance(resource_key, str)
        assert isinstance(resource_value, (int, float, str, bool))
