# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument


import asyncio
import logging
import re
from asyncio import BaseEventLoop
from contextlib import asynccontextmanager, contextmanager
from importlib import reload
from typing import AsyncGenerator, Callable, Iterator, List, Type
from unittest.mock import AsyncMock

import httpx
import pytest
import respx
from _pytest.monkeypatch import MonkeyPatch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pytest_mock.plugin import MockerFixture
from respx.router import MockRouter
from simcore_service_director_v2.core.settings import AppSettings
from simcore_service_director_v2.models.schemas.dynamic_services import (
    DynamicSidecarStatus,
    MonitorData,
    RunningDynamicServiceDetails,
    ServiceState,
)
from simcore_service_director_v2.modules.dynamic_sidecar import module_setup
from simcore_service_director_v2.modules.dynamic_sidecar.client_api import (
    get_url,
    setup_api_client,
    shutdown_api_client,
)
from simcore_service_director_v2.modules.dynamic_sidecar.errors import (
    DynamicSidecarError,
    DynamicSidecarNotFoundError,
)
from simcore_service_director_v2.modules.dynamic_sidecar.monitor import (
    DynamicSidecarsMonitor,
    setup_monitor,
    shutdown_monitor,
    task,
)
from simcore_service_director_v2.modules.dynamic_sidecar.monitor.events import (
    REGISTERED_EVENTS,
    MonitorEvent,
)

# running monitor at a hight rate to stress out the system
# and ensure faster tests
TEST_MONITOR_INTERVAL_SECONDS = 0.01
SLEEP_TO_AWAIT_MONITOR_TRIGGERS = 10 * TEST_MONITOR_INTERVAL_SECONDS

pytestmark = pytest.mark.asyncio

log = logging.getLogger(__name__)


# UTILS


@contextmanager
def _mock_containers_docker_status(
    monitor_data: MonitorData, expected_response: httpx.Response
) -> Iterator[MockRouter]:
    service_endpoint = monitor_data.dynamic_sidecar.endpoint
    with respx.mock as mock:
        mock.get(
            re.compile(
                fr"^http://{monitor_data.service_name}:{monitor_data.dynamic_sidecar.port}/v1/containers\?only_status=true"
            ),
            name="containers_docker_status",
        ).mock(return_value=expected_response)

        mock.post(
            get_url(service_endpoint, "/v1/containers:down"),
            name="begin_service_destruction",
        ).respond(text="")

        yield mock


@asynccontextmanager
async def _assert_get_dynamic_services_mocked(
    monitor: DynamicSidecarsMonitor,
    monitor_data: MonitorData,
    mock_service_running: AsyncMock,
    expected_response: httpx.Response,
) -> AsyncGenerator[RunningDynamicServiceDetails, None]:
    with _mock_containers_docker_status(monitor_data, expected_response):
        await monitor.add_service_to_monitor(monitor_data)

        stack_status = await monitor.get_stack_status(monitor_data.node_uuid)
        assert mock_service_running.called

        yield stack_status

        await monitor.remove_service_from_monitor(monitor_data.node_uuid, True)


# FIXTURES


@pytest.fixture
def mocked_monitor_events() -> None:
    class AlwaysTriggersMonitorEvent(MonitorEvent):
        @classmethod
        async def will_trigger(cls, app: FastAPI, monitor_data: MonitorData) -> bool:
            return True

        @classmethod
        async def action(cls, app: FastAPI, monitor_data: MonitorData) -> None:
            message = f"{cls.__name__} action triggered"
            log.warning(message)

    test_defined_monitor_events: List[Type[MonitorEvent]] = [AlwaysTriggersMonitorEvent]

    # add to REGISTERED_EVENTS
    for event in test_defined_monitor_events:
        REGISTERED_EVENTS.append(event)

    yield

    # make sure to cleanup and remove them after usage
    for event in test_defined_monitor_events:
        REGISTERED_EVENTS.remove(event)


@pytest.fixture
def ensure_monitor_runs_once() -> Callable:
    async def check_monitor_ran_once() -> None:
        await asyncio.sleep(SLEEP_TO_AWAIT_MONITOR_TRIGGERS)

    return check_monitor_ran_once


@pytest.fixture
def dynamic_sidecar_settings(monkeypatch: MonkeyPatch) -> AppSettings:
    monkeypatch.setenv("DYNAMIC_SIDECAR_IMAGE", "local/dynamic-sidecar:MOCKED")
    monkeypatch.setenv("POSTGRES_HOST", "mocked_out")
    monkeypatch.setenv("POSTGRES_USER", "mocked_out")
    monkeypatch.setenv("POSTGRES_PASSWORD", "mocked_out")
    monkeypatch.setenv("POSTGRES_DB", "mocked_out")
    monkeypatch.setenv("DIRECTOR_HOST", "mocked_out")
    monkeypatch.setenv("SC_BOOT_MODE", "local-development")
    monkeypatch.setenv(
        "DIRECTOR_V2_MONITOR_INTERVAL_SECONDS", str(TEST_MONITOR_INTERVAL_SECONDS)
    )

    app_settings = AppSettings.create_from_env()
    return app_settings


@pytest.fixture
async def mocked_app(
    loop: BaseEventLoop, dynamic_sidecar_settings: AppSettings
) -> Iterator[FastAPI]:
    app = FastAPI()
    app.state.settings = dynamic_sidecar_settings
    try:
        await setup_api_client(app)
        await setup_monitor(app)

        yield app

    finally:
        await shutdown_api_client(app)
        await shutdown_monitor(app)


@pytest.fixture
def monitor(mocked_app: FastAPI) -> DynamicSidecarsMonitor:
    return mocked_app.state.dynamic_sidecar_monitor


@pytest.fixture
def monitor_data(monitor_data_from_http_request: MonitorData) -> MonitorData:
    return monitor_data_from_http_request


@pytest.fixture
def mocked_client_api(monitor_data: MonitorData) -> MockRouter:
    service_endpoint = monitor_data.dynamic_sidecar.endpoint
    with respx.mock as mock:
        mock.get(get_url(service_endpoint, "/health"), name="is_healthy").respond(
            json=dict(is_healthy=True)
        )
        mock.post(
            get_url(service_endpoint, "/v1/containers:down"),
            name="begin_service_destruction",
        ).respond(text="")

        yield mock


@pytest.fixture
def mock_service_running(mocker: MockerFixture) -> AsyncMock:
    mock = mocker.patch(
        "simcore_service_director_v2.modules.dynamic_sidecar.docker_api.get_dynamic_sidecar_state",
        return_value=(ServiceState.RUNNING, ""),
    )
    reload(task)

    yield mock


@pytest.fixture
def mock_max_status_api_duration(monkeypatch: MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("DIRECTOR_V2_MONITOR_MAX_STATUS_API_DURATION", "0.0001")
    yield


# TESTS


async def test_monitor_add_remove(
    ensure_monitor_runs_once: Callable,
    monitor: DynamicSidecarsMonitor,
    monitor_data: MonitorData,
    mocked_client_api: MockRouter,
    docker_swarm: None,
    mocked_monitor_events: None,
) -> None:
    await ensure_monitor_runs_once()
    await monitor.add_service_to_monitor(monitor_data)

    await ensure_monitor_runs_once()
    assert monitor_data.dynamic_sidecar.is_available is True

    await monitor.remove_service_from_monitor(monitor_data.node_uuid, True)


async def test_monitor_removes_partially_started_services(
    ensure_monitor_runs_once: Callable,
    monitor: DynamicSidecarsMonitor,
    monitor_data: MonitorData,
    docker_swarm: None,
    mocked_monitor_events: None,
) -> None:
    await ensure_monitor_runs_once()
    await monitor.add_service_to_monitor(monitor_data)

    monitor_data.dynamic_sidecar.were_services_created = True
    await ensure_monitor_runs_once()


async def test_monitor_is_failing(
    ensure_monitor_runs_once: Callable,
    monitor: DynamicSidecarsMonitor,
    monitor_data: MonitorData,
    docker_swarm: None,
    mocked_monitor_events: None,
) -> None:
    await ensure_monitor_runs_once()
    await monitor.add_service_to_monitor(monitor_data)

    monitor_data.dynamic_sidecar.status.current = DynamicSidecarStatus.FAILING
    await ensure_monitor_runs_once()


async def test_monitor_health_timing_out(
    ensure_monitor_runs_once: Callable,
    monitor: DynamicSidecarsMonitor,
    monitor_data: MonitorData,
    mock_max_status_api_duration: None,
    docker_swarm: None,
    mocked_monitor_events: None,
) -> None:

    await ensure_monitor_runs_once()
    await monitor.add_service_to_monitor(monitor_data)
    await ensure_monitor_runs_once()

    assert monitor_data.dynamic_sidecar.is_available == False


async def test_adding_service_two_times(
    monitor: DynamicSidecarsMonitor,
    monitor_data: MonitorData,
    docker_swarm: None,
    mocked_monitor_events: None,
) -> None:
    await monitor.add_service_to_monitor(monitor_data)
    await monitor.add_service_to_monitor(monitor_data)


async def test_collition_at_global_level(
    monitor: DynamicSidecarsMonitor,
    monitor_data: MonitorData,
    docker_swarm: None,
    mocked_monitor_events: None,
) -> None:
    # pylint: disable=protected-access
    monitor._inverse_search_mapping[monitor_data.node_uuid] = "mock_service_name"
    with pytest.raises(DynamicSidecarError) as execinfo:
        await monitor.add_service_to_monitor(monitor_data)
    assert "node_uuids at a global level collided." in str(execinfo.value)


async def test_no_service_name(
    monitor: DynamicSidecarsMonitor,
    monitor_data: MonitorData,
    docker_swarm: None,
    mocked_monitor_events: None,
) -> None:
    monitor_data.service_name = ""
    with pytest.raises(DynamicSidecarError) as execinfo:
        await monitor.add_service_to_monitor(monitor_data)
    assert "a service with no name is not valid. Invalid usage." == str(execinfo.value)


async def test_remove_missing_no_error(
    monitor: DynamicSidecarsMonitor,
    monitor_data: MonitorData,
    docker_swarm: None,
    mocked_monitor_events: None,
) -> None:
    with pytest.raises(DynamicSidecarNotFoundError) as execinfo:
        await monitor.remove_service_from_monitor(monitor_data.node_uuid, True)
    assert f"node {monitor_data.node_uuid} not found" == str(execinfo.value)


async def test_get_stack_status(
    ensure_monitor_runs_once: Callable,
    monitor: DynamicSidecarsMonitor,
    monitor_data: MonitorData,
    docker_swarm: None,
    mocked_monitor_events: None,
) -> None:
    await ensure_monitor_runs_once()

    await monitor.add_service_to_monitor(monitor_data)

    stack_status = await monitor.get_stack_status(monitor_data.node_uuid)
    assert stack_status == RunningDynamicServiceDetails.from_monitoring_status(
        node_uuid=monitor_data.node_uuid,
        monitor_data=monitor_data,
        service_state=ServiceState.PENDING,
        service_message="",
    )


async def test_get_stack_status_missing(
    monitor: DynamicSidecarsMonitor,
    monitor_data: MonitorData,
    docker_swarm: None,
    mocked_monitor_events: None,
) -> None:
    with pytest.raises(DynamicSidecarNotFoundError) as execinfo:
        await monitor.get_stack_status(monitor_data.node_uuid)
    assert f"node {monitor_data.node_uuid} not found" in str(execinfo)


async def test_get_stack_status_failing_sidecar(
    monitor: DynamicSidecarsMonitor,
    monitor_data: MonitorData,
    docker_swarm: None,
    mocked_monitor_events: None,
) -> None:
    failing_message = "some_failing_message"
    monitor_data.dynamic_sidecar.status.update_failing_status(failing_message)

    await monitor.add_service_to_monitor(monitor_data)

    stack_status = await monitor.get_stack_status(monitor_data.node_uuid)
    assert stack_status == RunningDynamicServiceDetails.from_monitoring_status(
        node_uuid=monitor_data.node_uuid,
        monitor_data=monitor_data,
        service_state=ServiceState.FAILED,
        service_message=failing_message,
    )


async def test_get_stack_status_report_missing_statuses(
    monitor: DynamicSidecarsMonitor,
    monitor_data: MonitorData,
    mock_service_running: AsyncMock,
    docker_swarm: None,
    mocked_monitor_events: None,
) -> None:
    async with _assert_get_dynamic_services_mocked(
        monitor,
        monitor_data,
        mock_service_running,
        expected_response=httpx.Response(400),
    ) as stack_status:
        assert stack_status == RunningDynamicServiceDetails.from_monitoring_status(
            node_uuid=monitor_data.node_uuid,
            monitor_data=monitor_data,
            service_state=ServiceState.STARTING,
            service_message="There was an error while trying to fetch the stautes form the contianers",
        )


async def test_get_stack_status_containers_are_starting(
    monitor: DynamicSidecarsMonitor,
    monitor_data: MonitorData,
    mock_service_running: AsyncMock,
    docker_swarm: None,
    mocked_monitor_events: None,
) -> None:
    async with _assert_get_dynamic_services_mocked(
        monitor,
        monitor_data,
        mock_service_running,
        expected_response=httpx.Response(200, json={}),
    ) as stack_status:
        assert stack_status == RunningDynamicServiceDetails.from_monitoring_status(
            node_uuid=monitor_data.node_uuid,
            monitor_data=monitor_data,
            service_state=ServiceState.STARTING,
            service_message="",
        )


async def test_get_stack_status_ok(
    monitor: DynamicSidecarsMonitor,
    monitor_data: MonitorData,
    mock_service_running: AsyncMock,
    docker_swarm: None,
    mocked_monitor_events: None,
) -> None:
    async with _assert_get_dynamic_services_mocked(
        monitor,
        monitor_data,
        mock_service_running,
        expected_response=httpx.Response(
            200, json={"fake_entry": {"Status": "fake_status"}}
        ),
    ) as stack_status:
        assert stack_status == RunningDynamicServiceDetails.from_monitoring_status(
            node_uuid=monitor_data.node_uuid,
            monitor_data=monitor_data,
            service_state=ServiceState.STARTING,
            service_message="",
        )


async def test_module_setup(dynamic_sidecar_settings: AppSettings) -> None:
    app = FastAPI()
    app.state.settings = dynamic_sidecar_settings
    module_setup.setup(app)
    with TestClient(app):
        pass
