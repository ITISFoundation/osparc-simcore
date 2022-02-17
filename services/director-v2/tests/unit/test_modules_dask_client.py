# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access
# pylint:disable=too-many-arguments

import asyncio
import functools
import json
import time
from dataclasses import dataclass
from typing import Any, AsyncIterator, Awaitable, Callable, Dict, List, Optional
from unittest import mock
from uuid import uuid4

import distributed
import pytest
from _dask_helpers import DaskGatewayServer
from _pytest.monkeypatch import MonkeyPatch
from dask.distributed import get_worker
from dask_task_models_library.container_tasks.docker import DockerBasicAuth
from dask_task_models_library.container_tasks.events import (
    TaskCancelEvent,
    TaskStateEvent,
)
from dask_task_models_library.container_tasks.io import (
    TaskInputData,
    TaskOutputData,
    TaskOutputDataSchema,
)
from distributed import Event, Scheduler, Sub
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
    ComputationalSchedulerChangedError,
    InsuficientComputationalResourcesError,
    MissingComputationalResourcesError,
)
from simcore_service_director_v2.models.domains.comp_tasks import Image
from simcore_service_director_v2.models.schemas.constants import ClusterID, UserID
from simcore_service_director_v2.models.schemas.services import NodeRequirements
from simcore_service_director_v2.modules.dask_client import DaskClient
from tenacity._asyncio import AsyncRetrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed, wait_random
from yarl import URL

_ALLOW_TIME_FOR_GATEWAY_TO_CREATE_WORKERS = 20


async def _wait_for_call(mocked_fct, timeout: Optional[int] = None):
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
        assert client.cancellation_dask_pub
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
        assert client.cancellation_dask_pub
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
async def mocked_user_completed_cb(mocker: MockerFixture) -> mock.AsyncMock:
    return mocker.AsyncMock()


async def test_dask_cluster_executes_simple_functions(
    loop: asyncio.AbstractEventLoop, dask_client: DaskClient
):
    def test_fct_add(x: int, y: int) -> int:
        return x + y

    future = dask_client.dask_subsystem.client.submit(test_fct_add, 2, 5)
    assert future

    result = await future.result(timeout=_ALLOW_TIME_FOR_GATEWAY_TO_CREATE_WORKERS)  # type: ignore
    assert result == 7


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
    # this waits for the computation to run
    await _wait_for_call(
        mocked_user_completed_cb, timeout=_ALLOW_TIME_FOR_GATEWAY_TO_CREATE_WORKERS
    )
    mocked_user_completed_cb.assert_called_once()
    mocked_user_completed_cb.assert_called_with(
        TaskStateEvent(
            job_id=job_id,
            msg=json.dumps({"some_output_key": 123}),
            state=RunningState.SUCCESS,
        )
    )


async def test_abort_send_computation_task(
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
        expected_annotations: Dict[str, Any],
    ) -> TaskOutputData:
        sub = Sub(TaskCancelEvent.topic_name())
        # get the task data
        worker = get_worker()
        task = worker.tasks.get(worker.get_current_task())
        assert task is not None
        print(f"--> task {task=} started")
        assert task.annotations == expected_annotations
        # tell the client we are started
        start_event = Event(_DASK_EVENT_NAME)
        start_event.set()
        # sleep a bit in case someone is aborting us
        print("--> waiting for task to be aborted...")
        for msg in sub:
            assert msg
            print(f"--> received cancellation msg: {msg=}")
            cancel_event = TaskCancelEvent.parse_raw(msg)  # type: ignore
            assert cancel_event
            if cancel_event.job_id == task.key:
                print("--> raising cancellation error now")
                raise asyncio.CancelledError("task cancelled")

        return TaskOutputData.parse_obj({"some_output_key": 123})

    node_id_to_job_ids = await dask_client.send_computation_tasks(
        user_id=user_id,
        project_id=project_id,
        cluster_id=cluster_id,
        tasks=image_params.fake_tasks,
        callback=mocked_user_completed_cb,
        remote_fct=functools.partial(
            fake_remote_fct, expected_annotations=image_params.expected_annotations
        ),
    )
    assert node_id_to_job_ids
    assert len(node_id_to_job_ids) == 1
    node_id, job_id = node_id_to_job_ids[0]
    assert node_id in image_params.fake_tasks

    start_event = Event(_DASK_EVENT_NAME)
    await start_event.wait(timeout=10)  # type: ignore

    # now let's abort the computation
    await dask_client.abort_computation_tasks([job_id])
    await _wait_for_call(mocked_user_completed_cb)
    mocked_user_completed_cb.assert_called_once()
    mocked_user_completed_cb.assert_called_with(
        TaskStateEvent(
            job_id=job_id,
            msg=None,
            state=RunningState.ABORTED,
        )
    )


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
    await _wait_for_call(
        mocked_user_completed_cb, timeout=_ALLOW_TIME_FOR_GATEWAY_TO_CREATE_WORKERS
    )
    mocked_user_completed_cb.assert_called_once()
    assert mocked_user_completed_cb.call_args[0][0].job_id == job_id
    assert mocked_user_completed_cb.call_args[0][0].state == RunningState.FAILED
    mocked_user_completed_cb.call_args[0][0].msg.find("Traceback")
    mocked_user_completed_cb.call_args[0][0].msg.find("raise ValueError")


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

    # depending on speed, this will be pending first
    async def _wait_for_task_status(expected_status: RunningState):
        async for attempt in AsyncRetrying(
            reraise=True,
            stop=stop_after_delay(_ALLOW_TIME_FOR_GATEWAY_TO_CREATE_WORKERS),
            wait=wait_fixed(1),
        ):
            with attempt:
                print(
                    f"waiting for task to be {expected_status=}, "
                    f"Attempt={attempt.retry_state.attempt_number}"
                )
                tasks_status = await dask_client.get_tasks_status([job_id])
                assert tasks_status
                assert len(tasks_status) == 1
                print(f"current {tasks_status=}")
                assert tasks_status[0] == expected_status

    await _wait_for_task_status(RunningState.STARTED)

    # let the remote fct run through now
    start_event = Event(_DASK_EVENT_NAME, dask_client.dask_subsystem.client)
    await start_event.set()  # type: ignore
    # it will become successful hopefuly
    await _wait_for_task_status(
        RunningState.FAILED if fail_remote_fct else RunningState.SUCCESS
    )

    # removing the future will let dask eventually delete the task from its memory, so its status becomes undefined
    del computation_future
    await _wait_for_task_status(RunningState.UNKNOWN)


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
