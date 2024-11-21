# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=no-member


import asyncio
import json
from collections.abc import AsyncIterable, Callable
from pathlib import Path
from typing import Any, Final
from unittest.mock import AsyncMock

import aiodocker
import pytest
from aiodocker.containers import DockerContainer
from aiodocker.utils import clean_filters
from aiodocker.volumes import DockerVolume
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from httpx import AsyncClient
from models_library.generated_models.docker_rest_api import ContainerState
from models_library.generated_models.docker_rest_api import Status2 as ContainerStatus
from models_library.rabbitmq_messages import (
    RabbitResourceTrackingHeartbeatMessage,
    RabbitResourceTrackingMessages,
    RabbitResourceTrackingStartedMessage,
    RabbitResourceTrackingStoppedMessage,
    SimcorePlatformStatus,
)
from models_library.services_creation import CreateServiceMetricsAdditionalParams
from pydantic import AnyHttpUrl, TypeAdapter
from pytest_mock import MockerFixture
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict, setenvs_from_dict
from servicelib.fastapi.long_running_tasks.client import (
    Client,
    TaskClientResultError,
    TaskId,
    periodic_task_result,
)
from servicelib.fastapi.long_running_tasks.client import setup as client_setup
from simcore_service_dynamic_sidecar._meta import API_VTAG
from simcore_service_dynamic_sidecar.core.docker_utils import get_container_states
from simcore_service_dynamic_sidecar.models.schemas.containers import (
    ContainersComposeSpec,
    ContainersCreate,
)
from simcore_service_dynamic_sidecar.models.shared_store import SharedStore
from tenacity import AsyncRetrying, TryAgain
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

_FAST_STATUS_POLL: Final[float] = 0.1
_CREATE_SERVICE_CONTAINERS_TIMEOUT: Final[float] = 60
_BASE_HEART_BEAT_INTERVAL: Final[float] = 0.1


@pytest.fixture(params=[1, 2])
def container_names(request: pytest.FixtureRequest) -> list[str]:
    return [f"service-{i}" for i in range(request.param)]


@pytest.fixture
def raw_compose_spec(container_names: list[str]) -> dict[str, Any]:
    base_spec: dict[str, Any] = {"version": "3", "services": {}}

    for container_name in container_names:
        base_spec["services"][container_name] = {
            "image": "alpine:latest",
            "command": ["sh", "-c", "sleep 100000"],
        }

    return base_spec


@pytest.fixture
def compose_spec(raw_compose_spec: dict[str, Any]) -> str:
    return json.dumps(raw_compose_spec)


@pytest.fixture
def backend_url() -> AnyHttpUrl:
    return TypeAdapter(AnyHttpUrl).validate_python("http://backgroud.testserver.io")


@pytest.fixture
def mock_environment(
    monkeypatch: pytest.MonkeyPatch, mock_rabbitmq_envs: EnvVarsDict
) -> EnvVarsDict:
    setenvs_from_dict(
        monkeypatch,
        {"RESOURCE_TRACKING_HEARTBEAT_INTERVAL": f"{_BASE_HEART_BEAT_INTERVAL}"},
    )
    return mock_rabbitmq_envs


@pytest.fixture
async def app(app: FastAPI) -> AsyncIterable[FastAPI]:
    # add the client setup to the same application
    # this is only required for testing, in reality
    # this will be in a different process
    client_setup(app)
    async with LifespanManager(app):
        yield app


@pytest.fixture
async def httpx_async_client(
    app: FastAPI,
    backend_url: AnyHttpUrl,
    ensure_external_volumes: tuple[DockerVolume],
    cleanup_containers: None,
    ensure_shared_store_dir: Path,
) -> AsyncIterable[AsyncClient]:
    # crete dir here
    async with AsyncClient(
        app=app, base_url=f"{backend_url}", headers={"Content-Type": "application/json"}
    ) as client:
        yield client


@pytest.fixture
def client(
    app: FastAPI, httpx_async_client: AsyncClient, backend_url: AnyHttpUrl
) -> Client:
    return Client(app=app, async_client=httpx_async_client, base_url=f"{backend_url}")


@pytest.fixture
def mock_user_services_fail_to_start(mocker: MockerFixture) -> None:
    mocker.patch(
        "simcore_service_dynamic_sidecar.modules.long_running_tasks._retry_docker_compose_create",
        side_effect=RuntimeError(""),
    )


@pytest.fixture
def mock_user_services_fail_to_stop(mocker: MockerFixture) -> None:
    mocker.patch(
        "simcore_service_dynamic_sidecar.modules.long_running_tasks._retry_docker_compose_down",
        side_effect=RuntimeError(""),
    )


async def _get_task_id_create_service_containers(
    httpx_async_client: AsyncClient,
    compose_spec: str,
    mock_metrics_params: CreateServiceMetricsAdditionalParams,
) -> TaskId:
    containers_compose_spec = ContainersComposeSpec(
        docker_compose_yaml=compose_spec,
    )
    await httpx_async_client.post(
        f"/{API_VTAG}/containers/compose-spec",
        json=containers_compose_spec.model_dump(),
    )
    containers_create = ContainersCreate(metrics_params=mock_metrics_params)
    response = await httpx_async_client.post(
        f"/{API_VTAG}/containers", json=containers_create.model_dump()
    )
    task_id: TaskId = response.json()
    assert isinstance(task_id, str)
    return task_id


async def _get_task_id_docker_compose_down(httpx_async_client: AsyncClient) -> TaskId:
    response = await httpx_async_client.post(f"/{API_VTAG}/containers:down")
    task_id: TaskId = response.json()
    assert isinstance(task_id, str)
    return task_id


def _get_resource_tracking_messages(
    mock_core_rabbitmq: dict[str, AsyncMock]
) -> list[RabbitResourceTrackingMessages]:
    return [
        x[0][1]
        for x in mock_core_rabbitmq["post_rabbit_message"].call_args_list
        if isinstance(x[0][1], RabbitResourceTrackingMessages)
    ]


async def _wait_for_containers_to_be_running(app: FastAPI) -> None:
    shared_store: SharedStore = app.state.shared_store
    async for attempt in AsyncRetrying(wait=wait_fixed(0.1), stop=stop_after_delay(4)):
        with attempt:
            containers_statuses = await get_container_states(
                shared_store.container_names
            )

            running_container_statuses = [
                x
                for x in containers_statuses.values()
                if x is not None and x.status == ContainerStatus.running
            ]

            if len(running_container_statuses) != len(shared_store.container_names):
                raise TryAgain


async def test_service_starts_and_closes_as_expected(
    mock_core_rabbitmq: dict[str, AsyncMock],
    app: FastAPI,
    httpx_async_client: AsyncClient,
    client: Client,
    compose_spec: str,
    container_names: list[str],
    mock_metrics_params: CreateServiceMetricsAdditionalParams,
):
    async with periodic_task_result(
        client=client,
        task_id=await _get_task_id_create_service_containers(
            httpx_async_client, compose_spec, mock_metrics_params
        ),
        task_timeout=_CREATE_SERVICE_CONTAINERS_TIMEOUT,
        status_poll_interval=_FAST_STATUS_POLL,
    ) as result:
        assert isinstance(result, list)
        assert len(result) == len(container_names)

    await _wait_for_containers_to_be_running(app)

    async with periodic_task_result(
        client=client,
        task_id=await _get_task_id_docker_compose_down(httpx_async_client),
        task_timeout=_CREATE_SERVICE_CONTAINERS_TIMEOUT,
        status_poll_interval=_FAST_STATUS_POLL,
    ) as result:
        assert result is None

    # NOTE: task was not properly cancelled and events were still
    # generated. This is here to catch regressions.
    await asyncio.sleep(_BASE_HEART_BEAT_INTERVAL * 10)

    # Ensure messages arrive in the expected order
    resource_tracking_messages = _get_resource_tracking_messages(mock_core_rabbitmq)
    assert len(resource_tracking_messages) >= 3

    start_message = resource_tracking_messages[0]
    heart_beat_messages = resource_tracking_messages[1:-1]
    assert len(heart_beat_messages) > 0
    stop_message = resource_tracking_messages[-1]

    assert isinstance(start_message, RabbitResourceTrackingStartedMessage)
    for heart_beat_message in heart_beat_messages:
        assert isinstance(heart_beat_message, RabbitResourceTrackingHeartbeatMessage)
    assert isinstance(stop_message, RabbitResourceTrackingStoppedMessage)
    assert stop_message.simcore_platform_status == SimcorePlatformStatus.OK


@pytest.mark.parametrize("with_compose_down", [True, False])
async def test_user_services_fail_to_start(
    mock_core_rabbitmq: dict[str, AsyncMock],
    app: FastAPI,
    httpx_async_client: AsyncClient,
    client: Client,
    compose_spec: str,
    mock_metrics_params: CreateServiceMetricsAdditionalParams,
    with_compose_down: bool,
    mock_user_services_fail_to_start: None,
):
    with pytest.raises(TaskClientResultError):
        async with periodic_task_result(
            client=client,
            task_id=await _get_task_id_create_service_containers(
                httpx_async_client, compose_spec, mock_metrics_params
            ),
            task_timeout=_CREATE_SERVICE_CONTAINERS_TIMEOUT,
            status_poll_interval=_FAST_STATUS_POLL,
        ):
            ...
    shared_store: SharedStore = app.state.shared_store
    assert len(shared_store.container_names) == 0

    if with_compose_down:
        async with periodic_task_result(
            client=client,
            task_id=await _get_task_id_docker_compose_down(httpx_async_client),
            task_timeout=_CREATE_SERVICE_CONTAINERS_TIMEOUT,
            status_poll_interval=_FAST_STATUS_POLL,
        ) as result:
            assert result is None

    # no messages were sent
    resource_tracking_messages = _get_resource_tracking_messages(mock_core_rabbitmq)
    assert len(resource_tracking_messages) == 0


async def test_user_services_fail_to_stop_or_save_data(
    mock_core_rabbitmq: dict[str, AsyncMock],
    app: FastAPI,
    httpx_async_client: AsyncClient,
    client: Client,
    compose_spec: str,
    container_names: list[str],
    mock_metrics_params: CreateServiceMetricsAdditionalParams,
    mock_user_services_fail_to_stop: None,
):
    async with periodic_task_result(
        client=client,
        task_id=await _get_task_id_create_service_containers(
            httpx_async_client, compose_spec, mock_metrics_params
        ),
        task_timeout=_CREATE_SERVICE_CONTAINERS_TIMEOUT,
        status_poll_interval=_FAST_STATUS_POLL,
    ) as result:
        assert isinstance(result, list)
        assert len(result) == len(container_names)

    await _wait_for_containers_to_be_running(app)

    # let a few heartbeats pass
    await asyncio.sleep(_BASE_HEART_BEAT_INTERVAL * 2)

    # in case of manual intervention multiple stops will be sent
    _EXPECTED_STOP_MESSAGES = 4
    for _ in range(_EXPECTED_STOP_MESSAGES):
        with pytest.raises(TaskClientResultError):
            async with periodic_task_result(
                client=client,
                task_id=await _get_task_id_docker_compose_down(httpx_async_client),
                task_timeout=_CREATE_SERVICE_CONTAINERS_TIMEOUT,
                status_poll_interval=_FAST_STATUS_POLL,
            ):
                ...

    # Ensure messages arrive in the expected order
    resource_tracking_messages = _get_resource_tracking_messages(mock_core_rabbitmq)
    assert len(resource_tracking_messages) >= 3

    start_message = resource_tracking_messages[0]
    heart_beat_messages = resource_tracking_messages[1:-_EXPECTED_STOP_MESSAGES]
    assert len(heart_beat_messages) > 0
    stop_messages = resource_tracking_messages[-_EXPECTED_STOP_MESSAGES:]
    # NOTE: this is a situation where multiple stop events are sent out
    # since the stopping fails and the operation is repeated
    assert len(stop_messages) == _EXPECTED_STOP_MESSAGES

    assert isinstance(start_message, RabbitResourceTrackingStartedMessage)
    for heart_beat_message in heart_beat_messages:
        assert isinstance(heart_beat_message, RabbitResourceTrackingHeartbeatMessage)
    for stop_message in stop_messages:
        assert isinstance(stop_message, RabbitResourceTrackingStoppedMessage)
        assert stop_message.simcore_platform_status == SimcorePlatformStatus.OK


async def _simulate_container_crash(container_names: list[str]) -> None:
    async with aiodocker.Docker() as docker:
        filters = clean_filters({"name": container_names})
        containers: list[DockerContainer] = await docker.containers.list(
            all=True, filters=filters
        )
        for container in containers:
            await container.kill()


@pytest.fixture
def mock_one_container_oom_killed(mocker: MockerFixture) -> Callable[[], None]:
    def _mock() -> None:
        async def _mocked_get_container_states(
            container_names: list[str],
        ) -> dict[str, ContainerState | None]:
            results = await get_container_states(container_names)
            for result in results.values():
                if result:
                    result.oom_killed = True
                    result.status = ContainerStatus.exited
                break
            return results

        mocker.patch(
            "simcore_service_dynamic_sidecar.modules.long_running_tasks.get_container_states",
            side_effect=_mocked_get_container_states,
        )
        mocker.patch(
            "simcore_service_dynamic_sidecar.modules.resource_tracking._core.get_container_states",
            side_effect=_mocked_get_container_states,
        )

    return _mock


@pytest.mark.parametrize("expected_platform_state", SimcorePlatformStatus)
async def test_user_services_crash_when_running(
    mock_core_rabbitmq: dict[str, AsyncMock],
    app: FastAPI,
    httpx_async_client: AsyncClient,
    client: Client,
    compose_spec: str,
    container_names: list[str],
    mock_metrics_params: CreateServiceMetricsAdditionalParams,
    mock_one_container_oom_killed: Callable[[], None],
    expected_platform_state: SimcorePlatformStatus,
):
    async with periodic_task_result(
        client=client,
        task_id=await _get_task_id_create_service_containers(
            httpx_async_client, compose_spec, mock_metrics_params
        ),
        task_timeout=_CREATE_SERVICE_CONTAINERS_TIMEOUT,
        status_poll_interval=_FAST_STATUS_POLL,
    ) as result:
        assert isinstance(result, list)
        assert len(result) == len(container_names)

    await _wait_for_containers_to_be_running(app)

    # let a few heartbeats pass
    await asyncio.sleep(_BASE_HEART_BEAT_INTERVAL * 2)

    # crash the user services
    if expected_platform_state == SimcorePlatformStatus.OK:
        # was it oom killed, not our fault
        mock_one_container_oom_killed()
    else:
        # something else happened our fault and is bad
        await _simulate_container_crash(container_names)

    # check only start and heartbeats are present
    resource_tracking_messages = _get_resource_tracking_messages(mock_core_rabbitmq)
    assert len(resource_tracking_messages) >= 2

    start_message = resource_tracking_messages[0]
    heart_beat_messages = resource_tracking_messages[1:]

    assert isinstance(start_message, RabbitResourceTrackingStartedMessage)
    for heart_beat_message in heart_beat_messages:
        assert isinstance(heart_beat_message, RabbitResourceTrackingHeartbeatMessage)

    # reset mock
    await asyncio.sleep(_BASE_HEART_BEAT_INTERVAL * 2)
    mock_core_rabbitmq["post_rabbit_message"].reset_mock()

    # wait a bit more and check no further heartbeats are sent
    await asyncio.sleep(_BASE_HEART_BEAT_INTERVAL * 2)
    new_resource_tracking_messages = _get_resource_tracking_messages(mock_core_rabbitmq)
    assert len(new_resource_tracking_messages) == 0

    # sending stop events, and since there was an issue multiple stops
    # will be sent due to manual intervention
    _EXPECTED_STOP_MESSAGES = 4
    for _ in range(_EXPECTED_STOP_MESSAGES):
        async with periodic_task_result(
            client=client,
            task_id=await _get_task_id_docker_compose_down(httpx_async_client),
            task_timeout=_CREATE_SERVICE_CONTAINERS_TIMEOUT,
            status_poll_interval=_FAST_STATUS_POLL,
        ) as result:
            assert result is None

    resource_tracking_messages = _get_resource_tracking_messages(mock_core_rabbitmq)
    # NOTE: only 1 stop event arrives here since the stopping of the containers
    # was successful
    assert len(resource_tracking_messages) == 1

    for stop_message in resource_tracking_messages:
        assert isinstance(stop_message, RabbitResourceTrackingStoppedMessage)
        assert stop_message.simcore_platform_status == SimcorePlatformStatus.OK
