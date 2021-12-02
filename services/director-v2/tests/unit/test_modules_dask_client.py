# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access
# pylint:disable=too-many-arguments

import asyncio
import functools
import json
import random
import time
from dataclasses import dataclass
from typing import Any, Dict, List
from unittest import mock
from uuid import uuid4

import pytest
from _pytest.monkeypatch import MonkeyPatch
from dask.distributed import get_worker
from dask_task_models_library.container_tasks.docker import DockerBasicAuth
from dask_task_models_library.container_tasks.events import TaskStateEvent
from dask_task_models_library.container_tasks.io import (
    TaskInputData,
    TaskOutputData,
    TaskOutputDataSchema,
)
from distributed.deploy.spec import SpecCluster
from fastapi.applications import FastAPI
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.projects_state import RunningState
from pydantic import AnyUrl
from pydantic.tools import parse_obj_as
from pytest_mock.plugin import MockerFixture
from simcore_service_director_v2.core.application import init_app
from simcore_service_director_v2.core.errors import (
    ComputationalBackendNotConnectedError,
    ConfigurationError,
    InsuficientComputationalResourcesError,
    MissingComputationalResourcesError,
)
from simcore_service_director_v2.core.settings import AppSettings
from simcore_service_director_v2.models.domains.comp_tasks import Image
from simcore_service_director_v2.models.schemas.constants import ClusterID, UserID
from simcore_service_director_v2.models.schemas.services import NodeRequirements
from simcore_service_director_v2.modules.dask_client import (
    CLUSTER_RESOURCE_MOCK_USAGE,
    DaskClient,
)
from starlette.testclient import TestClient
from tenacity._asyncio import AsyncRetrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_random


async def _wait_for_call(mocked_fct):
    async for attempt in AsyncRetrying(
        stop=stop_after_delay(10),
        wait=wait_random(0, 1),
        retry=retry_if_exception_type(AssertionError),
        reraise=True,
    ):
        with attempt:
            print(
                f"waiting for call in mocked fct {mocked_fct}, "
                f"Attempt={attempt.retry_state.attempt_number}"
            )
            mocked_fct.assert_called_once()


@pytest.fixture
def minimal_dask_config(
    loop: asyncio.AbstractEventLoop,
    mock_env: None,
    project_env_devel_environment: Dict[str, Any],
    monkeypatch: MonkeyPatch,
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
    monkeypatch.setenv("SC_BOOT_MODE", "production")


def test_dask_client_missing_raises_configuration_error(
    minimal_dask_config: None, monkeypatch: MonkeyPatch
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
    return client


async def test_local_dask_cluster_through_client(dask_client: DaskClient):
    def test_fct_add(x: int, y: int) -> int:
        return x + y

    future = dask_client.client.submit(test_fct_add, 2, 5)
    assert future
    result = await future.result(timeout=2)
    assert result == 7


@pytest.fixture
def project_id() -> ProjectID:
    return uuid4()


@pytest.fixture
def node_id() -> NodeID:
    return uuid4()


@dataclass
class ImageParams:
    image: Image
    expected_annotations: Dict[str, Any]
    fake_task: Dict[NodeID, Image]


@pytest.fixture
def cpu_image(node_id: NodeID, cluster_id_resource_name: str) -> ImageParams:
    image = Image(
        name="simcore/services/comp/pytest/cpu_image",
        tag="1.5.5",
        node_requirements=NodeRequirements(CPU=1, RAM="128 MiB"),
    )
    return ImageParams(
        image=image,
        expected_annotations={
            "resources": {
                "CPU": 1.0,
                "RAM": 128 * 1024 * 1024,
                cluster_id_resource_name: CLUSTER_RESOURCE_MOCK_USAGE,
            }
        },
        fake_task={node_id: image},
    )


@pytest.fixture
def gpu_image(node_id: NodeID, cluster_id_resource_name: str) -> ImageParams:
    image = Image(
        name="simcore/services/comp/pytest/gpu_image",
        tag="1.4.7",
        node_requirements=NodeRequirements(CPU=1, GPU=1, RAM="256 MiB"),
    )
    return ImageParams(
        image=image,
        expected_annotations={
            "resources": {
                "CPU": 1.0,
                "GPU": 1.0,
                "RAM": 256 * 1024 * 1024,
                cluster_id_resource_name: CLUSTER_RESOURCE_MOCK_USAGE,
            },
        },
        fake_task={node_id: image},
    )


@pytest.fixture
def mpi_image(node_id: NodeID, cluster_id_resource_name: str) -> ImageParams:
    image = Image(
        name="simcore/services/comp/pytest/mpi_image",
        tag="1.4.5123",
        node_requirements=NodeRequirements(CPU=2, RAM="128 MiB", MPI=1),
    )
    return ImageParams(
        image=image,
        expected_annotations={
            "resources": {
                "CPU": 2.0,
                "MPI": 1.0,
                "RAM": 128 * 1024 * 1024,
                cluster_id_resource_name: CLUSTER_RESOURCE_MOCK_USAGE,
            },
        },
        fake_task={node_id: image},
    )


@pytest.fixture(params=[cpu_image.__name__, gpu_image.__name__, mpi_image.__name__])
def image_params(
    cpu_image: ImageParams, gpu_image: ImageParams, mpi_image: ImageParams, request
) -> ImageParams:
    return {
        "cpu_image": cpu_image,
        "gpu_image": gpu_image,
        "mpi_image": mpi_image,
    }[request.param]


@pytest.fixture()
def mocked_node_ports(mocker: MockerFixture):
    mocker.patch(
        "simcore_service_director_v2.modules.dask_client.compute_input_data",
        return_value=TaskInputData.parse_obj({}),
    )
    mocker.patch(
        "simcore_service_director_v2.modules.dask_client.compute_output_data_schema",
        return_value=TaskOutputDataSchema.parse_obj({}),
    )
    mocker.patch(
        "simcore_service_director_v2.modules.dask_client.compute_service_log_file_upload_link",
        return_value=parse_obj_as(AnyUrl, "file://undefined"),
    )


@pytest.fixture
async def mocked_user_completed_cb(mocker: MockerFixture) -> mock.AsyncMock:
    return mocker.AsyncMock()


async def test_send_computation_task(
    dask_client: DaskClient,
    user_id: UserID,
    project_id: ProjectID,
    cluster_id: ClusterID,
    image_params: ImageParams,
    mocked_node_ports: None,
    mocked_user_completed_cb: mock.AsyncMock,
):
    # NOTE: this must be inlined so that the test works,
    # the dask-worker must be able to import the function
    def fake_sidecar_fct(
        docker_auth: DockerBasicAuth,
        service_key: str,
        service_version: str,
        input_data: TaskInputData,
        output_data_keys: TaskOutputDataSchema,
        log_file_url: AnyUrl,
        command: List[str],
        expected_annotations: Dict[str, Any],
    ) -> TaskOutputData:
        # sleep a bit in case someone is aborting us
        time.sleep(1)
        # get the task data
        worker = get_worker()
        task = worker.tasks.get(worker.get_current_task())
        assert task is not None
        assert task.annotations == expected_annotations
        return TaskOutputData.parse_obj({"some_output_key": 123})

    # NOTE: We pass another fct so it can run in our localy created dask cluster
    await dask_client.send_computation_tasks(
        user_id=user_id,
        project_id=project_id,
        cluster_id=cluster_id,
        tasks=image_params.fake_task,
        callback=mocked_user_completed_cb,
        remote_fct=functools.partial(
            fake_sidecar_fct, expected_annotations=image_params.expected_annotations
        ),
    )
    assert (
        len(dask_client._taskid_to_future_map) == 1
    ), "dask client did not store the future of the task sent"

    job_id, future = list(dask_client._taskid_to_future_map.items())[0]
    # this waits for the computation to run
    task_result = await future.result(timeout=2)
    assert isinstance(task_result, TaskOutputData)
    assert task_result["some_output_key"] == 123
    assert future.key == job_id
    await _wait_for_call(mocked_user_completed_cb)
    mocked_user_completed_cb.assert_called_once()
    mocked_user_completed_cb.assert_called_with(
        TaskStateEvent(
            job_id=job_id,
            msg=json.dumps({"some_output_key": 123}),
            state=RunningState.SUCCESS,
        )
    )
    assert (
        len(dask_client._taskid_to_future_map) == 0
    ), "the list of futures was not cleaned correctly"


async def test_abort_send_computation_task(
    dask_client: DaskClient,
    user_id: UserID,
    project_id: ProjectID,
    cluster_id: ClusterID,
    image_params: ImageParams,
    mocked_node_ports: None,
    mocked_user_completed_cb: mock.AsyncMock,
):
    # NOTE: this must be inlined so that the test works,
    # the dask-worker must be able to import the function
    def fake_sidecar_fct(
        docker_auth: DockerBasicAuth,
        service_key: str,
        service_version: str,
        input_data: TaskInputData,
        output_data_keys: TaskOutputDataSchema,
        log_file_url: AnyUrl,
        command: List[str],
        expected_annotations: Dict[str, Any],
    ) -> TaskOutputData:
        # sleep a bit in case someone is aborting us
        time.sleep(1)
        # get the task data
        worker = get_worker()
        task = worker.tasks.get(worker.get_current_task())
        assert task is not None
        assert task.annotations == expected_annotations
        return TaskOutputData.parse_obj({"some_output_key": 123})

    await dask_client.send_computation_tasks(
        user_id=user_id,
        project_id=project_id,
        cluster_id=cluster_id,
        tasks=image_params.fake_task,
        callback=mocked_user_completed_cb,
        remote_fct=functools.partial(
            fake_sidecar_fct, expected_annotations=image_params.expected_annotations
        ),
    )
    assert (
        len(dask_client._taskid_to_future_map) == 1
    ), "dask client did not store the future of the task sent"

    job_id, future = list(dask_client._taskid_to_future_map.items())[0]
    # now let's abort the computation
    assert future.key == job_id
    await dask_client.abort_computation_tasks([job_id])
    assert future.cancelled() == True
    await _wait_for_call(mocked_user_completed_cb)
    mocked_user_completed_cb.assert_called_once()
    mocked_user_completed_cb.assert_called_with(
        TaskStateEvent(
            job_id=job_id,
            msg=None,
            state=RunningState.ABORTED,
        )
    )
    assert (
        len(dask_client._taskid_to_future_map) == 0
    ), "the list of futures was not cleaned correctly"


async def test_failed_task_returns_exceptions(
    dask_client: DaskClient,
    user_id: UserID,
    project_id: ProjectID,
    cluster_id: ClusterID,
    gpu_image: ImageParams,
    mocked_node_ports: None,
    mocked_user_completed_cb: mock.AsyncMock,
):
    # NOTE: this must be inlined so that the test works,
    # the dask-worker must be able to import the function
    def fake_failing_sidecar_fct(
        docker_auth: DockerBasicAuth,
        service_key: str,
        service_version: str,
        input_data: TaskInputData,
        output_data_keys: TaskOutputDataSchema,
        log_file_url: AnyUrl,
        command: List[str],
    ) -> TaskOutputData:

        raise ValueError(
            "sadly we are failing to execute anything cause we are dumb..."
        )

    await dask_client.send_computation_tasks(
        user_id=user_id,
        project_id=project_id,
        cluster_id=cluster_id,
        tasks=gpu_image.fake_task,
        callback=mocked_user_completed_cb,
        remote_fct=fake_failing_sidecar_fct,
    )
    assert (
        len(dask_client._taskid_to_future_map) == 1
    ), "dask client did not store the future of the task sent"

    job_id, future = list(dask_client._taskid_to_future_map.items())[0]
    # this waits for the computation to run
    with pytest.raises(ValueError):
        task_result = await future.result(timeout=2)
    await _wait_for_call(mocked_user_completed_cb)
    mocked_user_completed_cb.assert_called_once()
    assert mocked_user_completed_cb.call_args[0][0].job_id == job_id
    assert mocked_user_completed_cb.call_args[0][0].state == RunningState.FAILED
    mocked_user_completed_cb.call_args[0][0].msg.find("Traceback")
    mocked_user_completed_cb.call_args[0][0].msg.find("raise ValueError")


async def test_invalid_cluster_send_computation_task(
    dask_client: DaskClient,
    user_id: UserID,
    project_id: ProjectID,
    cluster_id: ClusterID,
    image_params: ImageParams,
    mocked_node_ports: None,
    mocked_user_completed_cb: mock.AsyncMock,
):
    with pytest.raises(MissingComputationalResourcesError):
        await dask_client.send_computation_tasks(
            user_id=user_id,
            project_id=project_id,
            cluster_id=random.randint(cluster_id + 1, 100),
            tasks=image_params.fake_task,
            callback=mocked_user_completed_cb,
            remote_fct=None,
        )
    assert (
        len(dask_client._taskid_to_future_map) == 0
    ), "dask client should not store any future here"
    mocked_user_completed_cb.assert_not_called()


async def test_too_many_resource_send_computation_task(
    dask_client: DaskClient,
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
    cluster_id: ClusterID,
    mocked_node_ports: None,
    mocked_user_completed_cb: mock.AsyncMock,
):
    # create an image that needs a huge amount of CPU
    image = Image(
        name="simcore/services/comp/pytest",
        tag="1.4.5",
        node_requirements=NodeRequirements(CPU=10000000000000000, RAM="128 MiB"),
    )
    fake_task = {node_id: image}

    # let's have a big number of CPUs
    with pytest.raises(InsuficientComputationalResourcesError):
        await dask_client.send_computation_tasks(
            user_id=user_id,
            project_id=project_id,
            cluster_id=cluster_id,
            tasks=fake_task,
            callback=mocked_user_completed_cb,
            remote_fct=None,
        )
    assert (
        len(dask_client._taskid_to_future_map) == 0
    ), "dask client should not store any future here"
    mocked_user_completed_cb.assert_not_called()


async def test_disconnected_backend_send_computation_task(
    dask_spec_local_cluster: SpecCluster,
    dask_client: DaskClient,
    user_id: UserID,
    project_id: ProjectID,
    cluster_id: ClusterID,
    cpu_image: ImageParams,
    mocked_node_ports: None,
    mocked_user_completed_cb: mock.AsyncMock,
):
    # DISCONNECT THE CLUSTER
    await dask_spec_local_cluster.close()  # type: ignore
    #
    with pytest.raises(ComputationalBackendNotConnectedError):
        await dask_client.send_computation_tasks(
            user_id=user_id,
            project_id=project_id,
            cluster_id=cluster_id,
            tasks=cpu_image.fake_task,
            callback=mocked_user_completed_cb,
            remote_fct=None,
        )
    assert (
        len(dask_client._taskid_to_future_map) == 0
    ), "dask client should not store any future here"
    mocked_user_completed_cb.assert_not_called()


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
