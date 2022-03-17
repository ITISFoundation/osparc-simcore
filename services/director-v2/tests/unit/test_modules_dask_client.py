# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access
# pylint:disable=too-many-arguments

import asyncio
import functools
import traceback
from dataclasses import dataclass
from typing import Any, AsyncIterator, Awaitable, Callable, Dict, List, Optional, Type
from unittest import mock
from uuid import uuid4

import distributed
import pytest
from _dask_helpers import DaskGatewayServer
from _pytest.monkeypatch import MonkeyPatch
from dask.distributed import get_worker
from dask_task_models_library.container_tasks.docker import DockerBasicAuth
from dask_task_models_library.container_tasks.errors import TaskCancelledError
from dask_task_models_library.container_tasks.events import (
    TaskLogEvent,
    TaskProgressEvent,
    TaskStateEvent,
)
from dask_task_models_library.container_tasks.io import (
    TaskCancelEventName,
    TaskInputData,
    TaskOutputData,
    TaskOutputDataSchema,
)
from distributed import Event, Scheduler
from distributed.deploy.spec import SpecCluster
from faker import Faker
from fastapi.applications import FastAPI
from models_library.clusters import NoAuthentication, SimpleAuthentication
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.projects_state import RunningState
from pydantic import AnyUrl, ByteSize
from pydantic.tools import parse_obj_as
from pytest_mock.plugin import MockerFixture
from simcore_service_director_v2.core.errors import (
    ComputationalBackendNotConnectedError,
    ComputationalBackendTaskNotFoundError,
    ComputationalSchedulerChangedError,
    InsuficientComputationalResourcesError,
    MissingComputationalResourcesError,
)
from simcore_service_director_v2.models.domains.comp_tasks import Image
from simcore_service_director_v2.models.schemas.constants import ClusterID, UserID
from simcore_service_director_v2.models.schemas.services import NodeRequirements
from simcore_service_director_v2.modules.dask_client import DaskClient, TaskHandlers
from tenacity._asyncio import AsyncRetrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed, wait_random
from yarl import URL

_ALLOW_TIME_FOR_GATEWAY_TO_CREATE_WORKERS = 20


async def _assert_wait_for_cb_call(mocked_fct, timeout: Optional[int] = None):
    async for attempt in AsyncRetrying(
        stop=stop_after_delay(timeout or 10),
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
            mocked_fct.assert_called_with()


async def _assert_wait_for_task_status(
    job_id: str,
    dask_client: DaskClient,
    expected_status: RunningState,
    timeout: Optional[int] = None,
):
    async for attempt in AsyncRetrying(
        reraise=True,
        stop=stop_after_delay(timeout or _ALLOW_TIME_FOR_GATEWAY_TO_CREATE_WORKERS),
        wait=wait_fixed(1),
    ):
        with attempt:
            print(
                f"waiting for task to be {expected_status=}, "
                f"Attempt={attempt.retry_state.attempt_number}"
            )
            current_task_status = await dask_client.get_task_status(job_id)
            assert isinstance(current_task_status, RunningState)
            print(f"{current_task_status=} vs {expected_status=}")
            assert current_task_status == expected_status


@pytest.fixture
def minimal_dask_config(
    mock_env: None,
    project_env_devel_environment: Dict[str, Any],
    monkeypatch: MonkeyPatch,
) -> None:
    """set a minimal configuration for testing the dask connection only"""
    monkeypatch.setenv("DIRECTOR_ENABLED", "0")
    monkeypatch.setenv("POSTGRES_ENABLED", "0")
    monkeypatch.setenv("REGISTRY_ENABLED", "0")
    monkeypatch.setenv("DIRECTOR_V2_DYNAMIC_SIDECAR_ENABLED", "false")
    monkeypatch.setenv("DIRECTOR_V0_ENABLED", "0")
    monkeypatch.setenv("DIRECTOR_V2_POSTGRES_ENABLED", "0")
    monkeypatch.setenv("DIRECTOR_V2_DASK_CLIENT_ENABLED", "1")
    monkeypatch.setenv("DIRECTOR_V2_DASK_SCHEDULER_ENABLED", "0")
    monkeypatch.setenv("SC_BOOT_MODE", "production")


@pytest.fixture
async def create_dask_client_from_scheduler(
    minimal_dask_config: None,
    dask_spec_local_cluster: SpecCluster,
    minimal_app: FastAPI,
) -> AsyncIterator[Callable[[], Awaitable[DaskClient]]]:
    created_clients = []

    async def factory() -> DaskClient:
        client = await DaskClient.create(
            app=minimal_app,
            settings=minimal_app.state.settings.DASK_SCHEDULER,
            endpoint=parse_obj_as(AnyUrl, dask_spec_local_cluster.scheduler_address),
            authentication=NoAuthentication(),
        )
        assert client
        assert client.app == minimal_app
        assert client.settings == minimal_app.state.settings.DASK_SCHEDULER
        assert not client._subscribed_tasks

        assert client.dask_subsystem.client
        assert not client.dask_subsystem.gateway
        assert not client.dask_subsystem.gateway_cluster
        scheduler_infos = client.dask_subsystem.client.scheduler_info()  # type: ignore
        print(
            f"--> Connected to scheduler via client {client=} to scheduler {scheduler_infos=}"
        )
        created_clients.append(client)
        return client

    yield factory
    await asyncio.gather(*[client.delete() for client in created_clients])
    print(f"<-- Disconnected scheduler clients {created_clients=}")


@pytest.fixture
async def create_dask_client_from_gateway(
    minimal_dask_config: None,
    local_dask_gateway_server: DaskGatewayServer,
    minimal_app: FastAPI,
) -> AsyncIterator[Callable[[], Awaitable[DaskClient]]]:
    created_clients = []

    async def factory() -> DaskClient:
        client = await DaskClient.create(
            app=minimal_app,
            settings=minimal_app.state.settings.DASK_SCHEDULER,
            endpoint=parse_obj_as(AnyUrl, local_dask_gateway_server.address),
            authentication=SimpleAuthentication(
                username="pytest_user", password=local_dask_gateway_server.password
            ),
        )
        assert client
        assert client.app == minimal_app
        assert client.settings == minimal_app.state.settings.DASK_SCHEDULER
        assert not client._subscribed_tasks

        assert client.dask_subsystem.client
        assert client.dask_subsystem.gateway
        assert client.dask_subsystem.gateway_cluster

        scheduler_infos = client.dask_subsystem.client.scheduler_info()  # type: ignore
        print(f"--> Connected to gateway {client.dask_subsystem.gateway=}")
        print(f"--> Cluster {client.dask_subsystem.gateway_cluster=}")
        print(f"--> Client {client=}")
        print(
            f"--> Cluster dashboard link {client.dask_subsystem.gateway_cluster.dashboard_link}"
        )
        created_clients.append(client)
        return client

    yield factory
    await asyncio.gather(*[client.delete() for client in created_clients])
    print(f"<-- Disconnected gateway clients {created_clients=}")


@pytest.fixture(
    params=["create_dask_client_from_scheduler", "create_dask_client_from_gateway"]
)
async def dask_client(
    create_dask_client_from_scheduler, create_dask_client_from_gateway, request
) -> DaskClient:
    return await {
        "create_dask_client_from_scheduler": create_dask_client_from_scheduler,
        "create_dask_client_from_gateway": create_dask_client_from_gateway,
    }[request.param]()


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
    fake_tasks: Dict[NodeID, Image]


@pytest.fixture
def cpu_image(node_id: NodeID) -> ImageParams:
    image = Image(
        name="simcore/services/comp/pytest/cpu_image",
        tag="1.5.5",
        node_requirements=NodeRequirements(
            CPU=1, RAM=parse_obj_as(ByteSize, "128 MiB"), GPU=None, MPI=None
        ),
    )  # type: ignore
    return ImageParams(
        image=image,
        expected_annotations={
            "resources": {
                "CPU": 1.0,
                "RAM": 128 * 1024 * 1024,
            }
        },
        fake_tasks={node_id: image},
    )


@pytest.fixture
def gpu_image(node_id: NodeID) -> ImageParams:
    image = Image(
        name="simcore/services/comp/pytest/gpu_image",
        tag="1.4.7",
        node_requirements=NodeRequirements(
            CPU=1, GPU=1, RAM=parse_obj_as(ByteSize, "256 MiB"), MPI=None
        ),
    )  # type: ignore
    return ImageParams(
        image=image,
        expected_annotations={
            "resources": {
                "CPU": 1.0,
                "GPU": 1.0,
                "RAM": 256 * 1024 * 1024,
            },
        },
        fake_tasks={node_id: image},
    )


@pytest.fixture
def mpi_image(node_id: NodeID) -> ImageParams:
    image = Image(
        name="simcore/services/comp/pytest/mpi_image",
        tag="1.4.5123",
        node_requirements=NodeRequirements(
            CPU=2, RAM=parse_obj_as(ByteSize, "128 MiB"), MPI=1, GPU=None
        ),
    )  # type: ignore
    return ImageParams(
        image=image,
        expected_annotations={
            "resources": {
                "CPU": 2.0,
                "MPI": 1.0,
                "RAM": 128 * 1024 * 1024,
            },
        },
        fake_tasks={node_id: image},
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
def mocked_user_completed_cb(mocker: MockerFixture) -> mock.MagicMock:
    return mocker.MagicMock()


async def test_dask_cluster_executes_simple_functions(dask_client: DaskClient):
    def test_fct_add(x: int, y: int) -> int:
        return x + y

    future = dask_client.dask_subsystem.client.submit(test_fct_add, 2, 5)
    assert future

    result = await future.result(timeout=_ALLOW_TIME_FOR_GATEWAY_TO_CREATE_WORKERS)  # type: ignore
    assert result == 7


@pytest.mark.xfail(
    reason="BaseException is not propagated back by dask [https://github.com/dask/distributed/issues/5846]"
)
@pytest.mark.parametrize(
    "dask_client", ["create_dask_client_from_scheduler"], indirect=True
)
async def test_dask_does_not_report_asyncio_cancelled_error_in_task(
    dask_client: DaskClient,
):
    def fct_that_raise_cancellation_error():
        import asyncio  # pylint: disable=reimported

        raise asyncio.CancelledError("task was cancelled, but dask does not care...")

    future = dask_client.dask_subsystem.client.submit(fct_that_raise_cancellation_error)
    # NOTE: Since asyncio.CancelledError is derived from BaseException and the worker code checks Exception only
    # this goes through...
    # The day this is fixed, this test should detect it... SAN would be happy to know about it.
    assert (
        await future.exception(timeout=_ALLOW_TIME_FOR_GATEWAY_TO_CREATE_WORKERS)  # type: ignore
        and future.cancelled() == True
    )


@pytest.mark.xfail(
    reason="BaseException is not propagated back by dask [https://github.com/dask/distributed/issues/5846]"
)
@pytest.mark.parametrize(
    "dask_client", ["create_dask_client_from_scheduler"], indirect=True
)
async def test_dask_does_not_report_base_exception_in_task(dask_client: DaskClient):
    def fct_that_raise_base_exception():

        raise BaseException("task triggers a base exception, but dask does not care...")

    future = dask_client.dask_subsystem.client.submit(fct_that_raise_base_exception)
    # NOTE: Since asyncio.CancelledError is derived from BaseException and the worker code checks Exception only
    # this goes through...
    # The day this is fixed, this test should detect it... SAN would be happy to know about it.
    assert (
        await future.exception(timeout=_ALLOW_TIME_FOR_GATEWAY_TO_CREATE_WORKERS)  # type: ignore
        and future.cancelled() == True
    )


@pytest.mark.parametrize("exc", [Exception, TaskCancelledError])
@pytest.mark.parametrize(
    "dask_client", ["create_dask_client_from_scheduler"], indirect=True
)
async def test_dask_does_report_any_non_base_exception_derived_error(
    dask_client: DaskClient, exc: Type[Exception]
):
    def fct_that_raise_exception():
        raise exc

    future = dask_client.dask_subsystem.client.submit(fct_that_raise_exception)
    # NOTE: Since asyncio.CancelledError does not work we define our own Exception derived cancellation
    task_exception = await future.exception(
        timeout=_ALLOW_TIME_FOR_GATEWAY_TO_CREATE_WORKERS
    )  # type: ignore
    assert task_exception
    assert isinstance(task_exception, exc)
    task_traceback = await future.traceback(timeout=_ALLOW_TIME_FOR_GATEWAY_TO_CREATE_WORKERS)  # type: ignore
    assert task_traceback
    trace = traceback.format_exception(
        type(task_exception), value=task_exception, tb=task_traceback
    )
    assert trace


async def test_send_computation_task(
    dask_client: DaskClient,
    user_id: UserID,
    project_id: ProjectID,
    cluster_id: ClusterID,
    image_params: ImageParams,
    mocked_node_ports: None,
    mocked_user_completed_cb: mock.AsyncMock,
    faker: Faker,
):
    _DASK_EVENT_NAME = faker.pystr()
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
        expected_annotations,
    ) -> TaskOutputData:
        # get the task data
        worker = get_worker()
        task = worker.tasks.get(worker.get_current_task())
        assert task is not None
        assert task.annotations == expected_annotations
        assert command == ["run"]
        event = distributed.Event(_DASK_EVENT_NAME)
        event.wait(timeout=5)

        return TaskOutputData.parse_obj({"some_output_key": 123})

    # NOTE: We pass another fct so it can run in our localy created dask cluster
    node_id_to_job_ids = await dask_client.send_computation_tasks(
        user_id=user_id,
        project_id=project_id,
        cluster_id=cluster_id,
        tasks=image_params.fake_tasks,
        callback=mocked_user_completed_cb,
        remote_fct=functools.partial(
            fake_sidecar_fct, expected_annotations=image_params.expected_annotations
        ),
    )
    assert node_id_to_job_ids
    assert len(node_id_to_job_ids) == 1
    node_id, job_id = node_id_to_job_ids[0]
    assert node_id in image_params.fake_tasks

    # check status goes to PENDING/STARTED
    await _assert_wait_for_task_status(
        job_id, dask_client, expected_status=RunningState.STARTED
    )

    # using the event we let the remote fct continue
    event = distributed.Event(_DASK_EVENT_NAME)
    await event.set()  # type: ignore
    await _assert_wait_for_cb_call(
        mocked_user_completed_cb, timeout=_ALLOW_TIME_FOR_GATEWAY_TO_CREATE_WORKERS
    )

    # check the task status
    await _assert_wait_for_task_status(
        job_id, dask_client, expected_status=RunningState.SUCCESS
    )

    # check the results
    task_result = await dask_client.get_task_result(job_id)
    assert isinstance(task_result, TaskOutputData)
    assert task_result.get("some_output_key") == 123

    # now release the results
    await dask_client.release_task_result(job_id)
    # check the status now
    await _assert_wait_for_task_status(
        job_id, dask_client, expected_status=RunningState.UNKNOWN, timeout=60
    )

    with pytest.raises(ComputationalBackendTaskNotFoundError):
        await dask_client.get_task_result(job_id)


async def test_computation_task_is_persisted_on_dask_scheduler(
    dask_client: DaskClient,
    user_id: UserID,
    project_id: ProjectID,
    cluster_id: ClusterID,
    image_params: ImageParams,
    mocked_node_ports: None,
    mocked_user_completed_cb: mock.AsyncMock,
):
    """rationale:
    When a task is submitted to the dask backend, a dask future is returned.
    If the dask future goes out of scope, then the task is forgotten by the dask backend. So if
    for some reason the client gets deleted, or the director-v2, then all the futures would
    be deleted, thus stopping all the computations.
    To aleviate this, it is possible to persist the futures directly in the dask-scheduler.

    When submitting a computation task, the future corresponding to that task is "published" on the scheduler.
    """
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
    ) -> TaskOutputData:
        # get the task data
        worker = get_worker()
        task = worker.tasks.get(worker.get_current_task())
        assert task is not None

        return TaskOutputData.parse_obj({"some_output_key": 123})

    # NOTE: We pass another fct so it can run in our localy created dask cluster
    node_id_to_job_ids = await dask_client.send_computation_tasks(
        user_id=user_id,
        project_id=project_id,
        cluster_id=cluster_id,
        tasks=image_params.fake_tasks,
        callback=mocked_user_completed_cb,
        remote_fct=fake_sidecar_fct,
    )
    assert node_id_to_job_ids
    assert len(node_id_to_job_ids) == 1
    node_id, job_id = node_id_to_job_ids[0]
    await _assert_wait_for_cb_call(
        mocked_user_completed_cb, timeout=_ALLOW_TIME_FOR_GATEWAY_TO_CREATE_WORKERS
    )
    # check the task status
    await _assert_wait_for_task_status(
        job_id, dask_client, expected_status=RunningState.SUCCESS
    )
    assert node_id in image_params.fake_tasks
    # creating a new future shows that it is not done????
    assert not distributed.Future(job_id).done()

    # as the task is published on the dask-scheduler when sending, it shall still be published on the dask scheduler
    list_of_persisted_datasets = await dask_client.dask_subsystem.client.list_datasets()  # type: ignore
    assert list_of_persisted_datasets
    assert isinstance(list_of_persisted_datasets, tuple)
    assert len(list_of_persisted_datasets) == 1
    assert job_id in list_of_persisted_datasets
    assert list_of_persisted_datasets[0] == job_id
    # get the persisted future from the scheduler back
    task_future = await dask_client.dask_subsystem.client.get_dataset(name=job_id)  # type: ignore
    assert task_future
    assert isinstance(task_future, distributed.Future)
    assert task_future.key == job_id
    # NOTE: the future was persisted BEFORE the computation was completed.. therefore it is not updated
    # this is a bit weird, but it is so, this assertion demonstrates it. we need to await the results.
    assert not task_future.done()
    task_result = await task_future.result(timeout=2)  # type: ignore
    # now the future is done
    assert task_future.done()
    assert isinstance(task_result, TaskOutputData)
    assert task_result.get("some_output_key") == 123
    # try to create another future and this one is already done
    assert distributed.Future(job_id).done()


async def test_abort_computation_tasks(
    dask_client: DaskClient,
    user_id: UserID,
    project_id: ProjectID,
    cluster_id: ClusterID,
    image_params: ImageParams,
    mocked_node_ports: None,
    mocked_user_completed_cb: mock.AsyncMock,
    faker: Faker,
):
    _DASK_EVENT_NAME = faker.pystr()
    # NOTE: this must be inlined so that the test works,
    # the dask-worker must be able to import the function
    def fake_remote_fct(
        docker_auth: DockerBasicAuth,
        service_key: str,
        service_version: str,
        input_data: TaskInputData,
        output_data_keys: TaskOutputDataSchema,
        log_file_url: AnyUrl,
        command: List[str],
    ) -> TaskOutputData:
        # get the task data
        worker = get_worker()
        task = worker.tasks.get(worker.get_current_task())
        assert task is not None
        print(f"--> task {task=} started")
        cancel_event = Event(TaskCancelEventName.format(task.key))
        # tell the client we are started
        start_event = Event(_DASK_EVENT_NAME)
        start_event.set()
        # sleep a bit in case someone is aborting us
        print("--> waiting for task to be aborted...")
        cancel_event.wait(timeout=10)
        if cancel_event.is_set():
            # NOTE: asyncio.CancelledError is not propagated back to the client...
            print("--> raising cancellation error now")
            raise TaskCancelledError

        return TaskOutputData.parse_obj({"some_output_key": 123})

    node_id_to_job_ids = await dask_client.send_computation_tasks(
        user_id=user_id,
        project_id=project_id,
        cluster_id=cluster_id,
        tasks=image_params.fake_tasks,
        callback=mocked_user_completed_cb,
        remote_fct=fake_remote_fct,
    )
    assert node_id_to_job_ids
    assert len(node_id_to_job_ids) == 1
    node_id, job_id = node_id_to_job_ids[0]
    assert node_id in image_params.fake_tasks
    await _assert_wait_for_task_status(job_id, dask_client, RunningState.STARTED)

    # we wait to be sure the remote fct is started
    start_event = Event(_DASK_EVENT_NAME)
    await start_event.wait(timeout=10)  # type: ignore

    # now let's abort the computation
    await dask_client.abort_computation_task(job_id)
    await _assert_wait_for_cb_call(mocked_user_completed_cb)
    await _assert_wait_for_task_status(job_id, dask_client, RunningState.ABORTED)

    # getting the results should throw the cancellation error
    with pytest.raises(TaskCancelledError):
        await dask_client.get_task_result(job_id)

    # after releasing the results, the task shall be UNKNOWN
    await dask_client.release_task_result(job_id)
    await _assert_wait_for_task_status(
        job_id, dask_client, RunningState.UNKNOWN, timeout=120
    )


@pytest.mark.flaky
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

    node_id_to_job_ids = await dask_client.send_computation_tasks(
        user_id=user_id,
        project_id=project_id,
        cluster_id=cluster_id,
        tasks=gpu_image.fake_tasks,
        callback=mocked_user_completed_cb,
        remote_fct=fake_failing_sidecar_fct,
    )
    assert node_id_to_job_ids
    assert len(node_id_to_job_ids) == 1
    node_id, job_id = node_id_to_job_ids[0]
    assert node_id in gpu_image.fake_tasks

    # this waits for the computation to run
    await _assert_wait_for_cb_call(
        mocked_user_completed_cb, timeout=_ALLOW_TIME_FOR_GATEWAY_TO_CREATE_WORKERS
    )

    # the computation status is FAILED
    await _assert_wait_for_task_status(
        job_id, dask_client, expected_status=RunningState.FAILED
    )
    with pytest.raises(
        ValueError,
        match="sadly we are failing to execute anything cause we are dumb...",
    ):
        await dask_client.get_task_result(job_id)

    await dask_client.release_task_result(job_id)
    await _assert_wait_for_task_status(
        job_id, dask_client, expected_status=RunningState.UNKNOWN, timeout=60
    )


# currently in the case of a dask-gateway we do not check for missing resources
@pytest.mark.parametrize(
    "dask_client", ["create_dask_client_from_scheduler"], indirect=True
)
async def test_missing_resource_send_computation_task(
    dask_spec_local_cluster: SpecCluster,
    dask_client: DaskClient,
    user_id: UserID,
    project_id: ProjectID,
    cluster_id: ClusterID,
    image_params: ImageParams,
    mocked_node_ports: None,
    mocked_user_completed_cb: mock.AsyncMock,
):

    # remove the workers that can handle mpi
    scheduler_info = dask_client.dask_subsystem.client.scheduler_info()
    assert scheduler_info
    # find mpi workers
    workers_to_remove = [
        worker_key
        for worker_key, worker_info in scheduler_info["workers"].items()
        if "MPI" in worker_info["resources"]
    ]
    await dask_client.dask_subsystem.client.retire_workers(workers=workers_to_remove)  # type: ignore
    await asyncio.sleep(5)  # a bit of time is needed so the cluster adapts

    # now let's adapt the task so it needs mpi
    image_params.image.node_requirements.mpi = 2

    with pytest.raises(MissingComputationalResourcesError):
        await dask_client.send_computation_tasks(
            user_id=user_id,
            project_id=project_id,
            cluster_id=cluster_id,
            tasks=image_params.fake_tasks,
            callback=mocked_user_completed_cb,
            remote_fct=None,
        )
    mocked_user_completed_cb.assert_not_called()


@pytest.mark.parametrize(
    "dask_client", ["create_dask_client_from_scheduler"], indirect=True
)
async def test_too_many_resources_send_computation_task(
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
        node_requirements=NodeRequirements(
            CPU=10000000000000000,
            RAM=parse_obj_as(ByteSize, "128 MiB"),
            MPI=None,
            GPU=None,
        ),
    )  # type: ignore
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

    mocked_user_completed_cb.assert_not_called()


async def test_disconnected_backend_raises_exception(
    dask_spec_local_cluster: SpecCluster,
    local_dask_gateway_server: DaskGatewayServer,
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
    await local_dask_gateway_server.server.cleanup()
    #
    with pytest.raises(ComputationalBackendNotConnectedError):
        await dask_client.send_computation_tasks(
            user_id=user_id,
            project_id=project_id,
            cluster_id=cluster_id,
            tasks=cpu_image.fake_tasks,
            callback=mocked_user_completed_cb,
            remote_fct=None,
        )
    mocked_user_completed_cb.assert_not_called()


@pytest.mark.parametrize(
    "dask_client", ["create_dask_client_from_scheduler"], indirect=True
)
async def test_changed_scheduler_raises_exception(
    dask_spec_local_cluster: SpecCluster,
    dask_client: DaskClient,
    user_id: UserID,
    project_id: ProjectID,
    cluster_id: ClusterID,
    cpu_image: ImageParams,
    mocked_node_ports: None,
    mocked_user_completed_cb: mock.AsyncMock,
):
    # change the scheduler (stop the current one and start another at the same address)
    scheduler_address = URL(dask_spec_local_cluster.scheduler_address)
    await dask_spec_local_cluster.close()  # type: ignore

    scheduler = {
        "cls": Scheduler,
        "options": {"dashboard_address": ":8787", "port": scheduler_address.port},
    }
    async with SpecCluster(
        scheduler=scheduler, asynchronous=True, name="pytest_cluster"
    ) as cluster:
        assert URL(cluster.scheduler_address) == scheduler_address

        # leave a bit of time to allow the client to reconnect automatically
        await asyncio.sleep(2)

        with pytest.raises(ComputationalSchedulerChangedError):
            await dask_client.send_computation_tasks(
                user_id=user_id,
                project_id=project_id,
                cluster_id=cluster_id,
                tasks=cpu_image.fake_tasks,
                callback=mocked_user_completed_cb,
                remote_fct=None,
            )
    mocked_user_completed_cb.assert_not_called()


@pytest.mark.parametrize("fail_remote_fct", [False, True])
async def test_get_tasks_status(
    dask_client: DaskClient,
    user_id: UserID,
    project_id: ProjectID,
    cluster_id: ClusterID,
    cpu_image: ImageParams,
    mocked_node_ports: None,
    mocked_user_completed_cb: mock.AsyncMock,
    faker: Faker,
    fail_remote_fct: bool,
):
    # NOTE: this must be inlined so that the test works,
    # the dask-worker must be able to import the function
    _DASK_EVENT_NAME = faker.pystr()

    def fake_remote_fct(
        docker_auth: DockerBasicAuth,
        service_key: str,
        service_version: str,
        input_data: TaskInputData,
        output_data_keys: TaskOutputDataSchema,
        log_file_url: AnyUrl,
        command: List[str],
    ) -> TaskOutputData:
        # wait here until the client allows us to continue
        start_event = Event(_DASK_EVENT_NAME)
        start_event.wait(timeout=5)
        if fail_remote_fct:
            raise ValueError("We fail because we're told to!")
        return TaskOutputData.parse_obj({"some_output_key": 123})

    node_id_to_job_ids = await dask_client.send_computation_tasks(
        user_id=user_id,
        project_id=project_id,
        cluster_id=cluster_id,
        tasks=cpu_image.fake_tasks,
        callback=mocked_user_completed_cb,
        remote_fct=fake_remote_fct,
    )
    assert node_id_to_job_ids
    assert len(node_id_to_job_ids) == 1
    node_id, job_id = node_id_to_job_ids[0]
    assert node_id in cpu_image.fake_tasks
    # let's get a dask future for the task here so dask will not remove the task from the scheduler at the end
    computation_future = distributed.Future(key=job_id)
    assert computation_future

    await _assert_wait_for_task_status(job_id, dask_client, RunningState.STARTED)

    # let the remote fct run through now
    start_event = Event(_DASK_EVENT_NAME, dask_client.dask_subsystem.client)
    await start_event.set()  # type: ignore
    # it will become successful hopefuly
    await _assert_wait_for_task_status(
        job_id,
        dask_client,
        RunningState.FAILED if fail_remote_fct else RunningState.SUCCESS,
    )
    # release the task results
    await dask_client.release_task_result(job_id)
    # the task is still present since we hold a future here
    await _assert_wait_for_task_status(
        job_id,
        dask_client,
        RunningState.FAILED if fail_remote_fct else RunningState.SUCCESS,
    )

    # removing the future will let dask eventually delete the task from its memory, so its status becomes undefined
    del computation_future
    await _assert_wait_for_task_status(
        job_id, dask_client, RunningState.UNKNOWN, timeout=60
    )


@pytest.fixture
async def fake_task_handlers(mocker: MockerFixture) -> TaskHandlers:
    return TaskHandlers(mocker.MagicMock(), mocker.MagicMock(), mocker.MagicMock())


async def test_dask_sub_handlers(
    dask_client: DaskClient,
    user_id: UserID,
    project_id: ProjectID,
    cluster_id: ClusterID,
    cpu_image: ImageParams,
    mocked_node_ports: None,
    mocked_user_completed_cb: mock.AsyncMock,
    fake_task_handlers: TaskHandlers,
):
    dask_client.register_handlers(fake_task_handlers)
    _DASK_START_EVENT = "start"

    def fake_remote_fct(
        docker_auth: DockerBasicAuth,
        service_key: str,
        service_version: str,
        input_data: TaskInputData,
        output_data_keys: TaskOutputDataSchema,
        log_file_url: AnyUrl,
        command: List[str],
    ) -> TaskOutputData:

        state_pub = distributed.Pub(TaskStateEvent.topic_name())
        progress_pub = distributed.Pub(TaskProgressEvent.topic_name())
        logs_pub = distributed.Pub(TaskLogEvent.topic_name())
        state_pub.put("my name is state")
        progress_pub.put("my name is progress")
        logs_pub.put("my name is logs")
        # tell the client we are done
        published_event = Event(name=_DASK_START_EVENT)
        published_event.set()

        return TaskOutputData.parse_obj({"some_output_key": 123})

    # run the computation
    node_id_to_job_ids = await dask_client.send_computation_tasks(
        user_id=user_id,
        project_id=project_id,
        cluster_id=cluster_id,
        tasks=cpu_image.fake_tasks,
        callback=mocked_user_completed_cb,
        remote_fct=fake_remote_fct,
    )
    assert node_id_to_job_ids
    assert len(node_id_to_job_ids) == 1
    node_id, job_id = node_id_to_job_ids[0]
    assert node_id in cpu_image.fake_tasks
    computation_future = distributed.Future(job_id)
    print("--> waiting for job to finish...")
    await distributed.wait(computation_future, timeout=_ALLOW_TIME_FOR_GATEWAY_TO_CREATE_WORKERS)  # type: ignore
    assert computation_future.done()
    print("job finished, now checking that we received the publications...")

    async for attempt in AsyncRetrying(
        reraise=True,
        wait=wait_fixed(1),
        stop=stop_after_delay(5),
    ):
        with attempt:
            print(
                f"waiting for call in mocked fct {fake_task_handlers}, "
                f"Attempt={attempt.retry_state.attempt_number}"
            )
            # we should have received data in our TaskHandlers
            fake_task_handlers.task_change_handler.assert_called_with(
                "my name is state"
            )
            fake_task_handlers.task_progress_handler.assert_called_with(
                "my name is progress"
            )
            fake_task_handlers.task_log_handler.assert_called_with("my name is logs")
    await _assert_wait_for_cb_call(mocked_user_completed_cb)
