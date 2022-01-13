# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument


import asyncio
import logging
import re
import urllib.parse
from contextlib import asynccontextmanager, contextmanager
from importlib import reload
from typing import AsyncGenerator, AsyncIterator, Callable, Iterator, List, Type, Union
from unittest.mock import AsyncMock

import httpx
import pytest
import respx
from _pytest.monkeypatch import MonkeyPatch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from models_library.service_settings_labels import SimcoreServiceLabels
from pytest_mock.plugin import MockerFixture
from respx.router import MockRouter
from simcore_service_director_v2.core.settings import AppSettings
from simcore_service_director_v2.models.schemas.dynamic_services import (
    DynamicSidecarStatus,
    RunningDynamicServiceDetails,
    SchedulerData,
    ServiceState,
)
from simcore_service_director_v2.modules.director_v0 import DirectorV0Client
from simcore_service_director_v2.modules.dynamic_sidecar import module_setup
from simcore_service_director_v2.modules.dynamic_sidecar.client_api import (
    get_url,
    setup_api_client,
)
from simcore_service_director_v2.modules.dynamic_sidecar.errors import (
    DynamicSidecarError,
    DynamicSidecarNotFoundError,
)
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler import (
    DynamicSidecarsScheduler,
    setup_scheduler,
    shutdown_scheduler,
    task,
)
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler.events import (
    REGISTERED_EVENTS,
    DynamicSchedulerEvent,
)

# running scheduler at a hight rate to stress out the system
# and ensure faster tests
TEST_SCHEDULER_INTERVAL_SECONDS = 0.01
SLEEP_TO_AWAIT_SCHEDULER_TRIGGERS = 10 * TEST_SCHEDULER_INTERVAL_SECONDS

log = logging.getLogger(__name__)


# UTILS


@contextmanager
def _mock_containers_docker_status(
    scheduler_data: SchedulerData,
    expected_response: Union[httpx.Response, httpx.HTTPError],
) -> Iterator[MockRouter]:
    mocked_params = {}
    if isinstance(expected_response, httpx.Response):
        mocked_params["return_value"] = expected_response
    else:
        mocked_params["side_effect"] = expected_response

    service_endpoint = scheduler_data.dynamic_sidecar.endpoint
    with respx.mock as mock:
        mock.get(
            re.compile(
                fr"^http://{scheduler_data.service_name}:{scheduler_data.dynamic_sidecar.port}/v1/containers\?only_status=true"
            ),
            name="containers_docker_status",
        ).mock(**mocked_params)

        mock.post(
            get_url(service_endpoint, "/v1/containers:down"),
            name="begin_service_destruction",
        ).respond(text="")

        yield mock


async def _assert_remove_service(
    scheduler: DynamicSidecarsScheduler, scheduler_data: SchedulerData
) -> None:
    # pylint: disable=protected-access
    await scheduler.mark_service_for_removal(scheduler_data.node_uuid, True)
    assert scheduler_data.service_name in scheduler._to_observe
    await scheduler.finish_service_removal(scheduler_data.node_uuid)
    assert scheduler_data.service_name not in scheduler._to_observe


@asynccontextmanager
async def _assert_get_dynamic_services_mocked(
    scheduler: DynamicSidecarsScheduler,
    scheduler_data: SchedulerData,
    mock_service_running: AsyncMock,
    expected_response: Union[httpx.Response, httpx.HTTPError],
) -> AsyncGenerator[RunningDynamicServiceDetails, None]:
    with _mock_containers_docker_status(scheduler_data, expected_response):
        await scheduler.add_service(scheduler_data)

        stack_status = await scheduler.get_stack_status(scheduler_data.node_uuid)
        assert mock_service_running.called

        yield stack_status

        await _assert_remove_service(scheduler, scheduler_data)


# FIXTURES


@pytest.fixture
def mocked_director_v0(
    dynamic_sidecar_settings: AppSettings, scheduler_data: SchedulerData
) -> MockRouter:
    endpoint = dynamic_sidecar_settings.DIRECTOR_V0.endpoint

    with respx.mock as mock:
        mock.get(
            re.compile(
                fr"^{endpoint}/services/{urllib.parse.quote_plus(scheduler_data.key)}/{scheduler_data.version}/labels"
            ),
            name="service labels",
        ).respond(
            json={"data": SimcoreServiceLabels.Config.schema_extra["examples"][0]}
        )
        yield mock


@pytest.fixture
def mocked_dynamic_scheduler_events() -> Iterator[None]:
    class AlwaysTriggersDynamicSchedulerEvent(DynamicSchedulerEvent):
        @classmethod
        async def will_trigger(
            cls, app: FastAPI, scheduler_data: SchedulerData
        ) -> bool:
            return True

        @classmethod
        async def action(cls, app: FastAPI, scheduler_data: SchedulerData) -> None:
            message = f"{cls.__name__} action triggered"
            log.warning(message)

    test_defined_scheduler_events: List[Type[DynamicSchedulerEvent]] = [
        AlwaysTriggersDynamicSchedulerEvent
    ]

    # add to REGISTERED_EVENTS
    for event in test_defined_scheduler_events:
        REGISTERED_EVENTS.append(event)

    yield

    # make sure to cleanup and remove them after usage
    for event in test_defined_scheduler_events:
        REGISTERED_EVENTS.remove(event)


@pytest.fixture
def ensure_scheduler_runs_once() -> Callable:
    async def check_scheduler_ran_once() -> None:
        await asyncio.sleep(SLEEP_TO_AWAIT_SCHEDULER_TRIGGERS)

    return check_scheduler_ran_once


@pytest.fixture
def dynamic_sidecar_settings(
    simcore_services_network_name: str, monkeypatch: MonkeyPatch
) -> AppSettings:
    monkeypatch.setenv("REGISTRY_AUTH", "false")
    monkeypatch.setenv("REGISTRY_USER", "test")
    monkeypatch.setenv("REGISTRY_PW", "test")
    monkeypatch.setenv("REGISTRY_SSL", "false")
    monkeypatch.setenv("SIMCORE_SERVICES_NETWORK_NAME", simcore_services_network_name)
    monkeypatch.setenv("TRAEFIK_SIMCORE_ZONE", "test_traefik_zone")
    monkeypatch.setenv("SWARM_STACK_NAME", "test_swarm_name")
    monkeypatch.setenv("DYNAMIC_SIDECAR_IMAGE", "local/dynamic-sidecar:MOCKED")
    monkeypatch.setenv("POSTGRES_HOST", "mocked_out")
    monkeypatch.setenv("POSTGRES_USER", "mocked_out")
    monkeypatch.setenv("POSTGRES_PASSWORD", "mocked_out")
    monkeypatch.setenv("POSTGRES_DB", "mocked_out")
    monkeypatch.setenv("DIRECTOR_HOST", "mocked_out")
    monkeypatch.setenv("SC_BOOT_MODE", "local-development")
    monkeypatch.setenv(
        "DIRECTOR_V2_DYNAMIC_SCHEDULER_INTERVAL_SECONDS",
        str(TEST_SCHEDULER_INTERVAL_SECONDS),
    )

    app_settings = AppSettings.create_from_envs()
    return app_settings


@pytest.fixture
async def mocked_app(
    dynamic_sidecar_settings: AppSettings,
    mocked_director_v0: MockRouter,
    docker_swarm: None,
) -> AsyncIterator[FastAPI]:
    app = FastAPI()
    app.state.settings = dynamic_sidecar_settings
    log.info("AppSettings=%s", dynamic_sidecar_settings)
    try:
        DirectorV0Client.create(
            app,
            client=httpx.AsyncClient(
                base_url=f"{dynamic_sidecar_settings.DIRECTOR_V0.endpoint}",
                timeout=dynamic_sidecar_settings.CLIENT_REQUEST.HTTP_CLIENT_REQUEST_TOTAL_TIMEOUT,
            ),
        )
        await setup_api_client(app)
        await setup_scheduler(app)

        yield app

    finally:
        await shutdown_scheduler(app)


@pytest.fixture
def scheduler(mocked_app: FastAPI) -> DynamicSidecarsScheduler:
    return mocked_app.state.dynamic_sidecar_scheduler


@pytest.fixture
def scheduler_data(scheduler_data_from_http_request: SchedulerData) -> SchedulerData:
    return scheduler_data_from_http_request


@pytest.fixture
def mocked_client_api(scheduler_data: SchedulerData) -> MockRouter:
    service_endpoint = scheduler_data.dynamic_sidecar.endpoint
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
    monkeypatch.setenv(
        "DIRECTOR_V2_DYNAMIC_SCHEDULER_MAX_STATUS_API_DURATION", "0.0001"
    )
    yield


# TESTS


async def test_scheduler_add_remove(
    loop: asyncio.AbstractEventLoop,
    ensure_scheduler_runs_once: Callable,
    scheduler: DynamicSidecarsScheduler,
    scheduler_data: SchedulerData,
    mocked_client_api: MockRouter,
    docker_swarm: None,
    mocked_dynamic_scheduler_events: None,
) -> None:
    await ensure_scheduler_runs_once()
    await scheduler.add_service(scheduler_data)

    await ensure_scheduler_runs_once()
    assert scheduler_data.dynamic_sidecar.is_available is True

    await _assert_remove_service(scheduler, scheduler_data)


async def test_scheduler_removes_partially_started_services(
    loop: asyncio.AbstractEventLoop,
    ensure_scheduler_runs_once: Callable,
    scheduler: DynamicSidecarsScheduler,
    scheduler_data: SchedulerData,
    docker_swarm: None,
    mocked_dynamic_scheduler_events: None,
) -> None:
    await ensure_scheduler_runs_once()
    await scheduler.add_service(scheduler_data)

    scheduler_data.dynamic_sidecar.were_services_created = True
    await ensure_scheduler_runs_once()


async def test_scheduler_is_failing(
    loop: asyncio.AbstractEventLoop,
    ensure_scheduler_runs_once: Callable,
    scheduler: DynamicSidecarsScheduler,
    scheduler_data: SchedulerData,
    docker_swarm: None,
    mocked_dynamic_scheduler_events: None,
) -> None:
    await ensure_scheduler_runs_once()
    await scheduler.add_service(scheduler_data)

    scheduler_data.dynamic_sidecar.status.current = DynamicSidecarStatus.FAILING
    await ensure_scheduler_runs_once()


async def test_scheduler_health_timing_out(
    loop: asyncio.AbstractEventLoop,
    ensure_scheduler_runs_once: Callable,
    scheduler: DynamicSidecarsScheduler,
    scheduler_data: SchedulerData,
    mock_max_status_api_duration: None,
    docker_swarm: None,
    mocked_dynamic_scheduler_events: None,
) -> None:

    await ensure_scheduler_runs_once()
    await scheduler.add_service(scheduler_data)
    await ensure_scheduler_runs_once()

    assert scheduler_data.dynamic_sidecar.is_available is False


async def test_adding_service_two_times(
    loop: asyncio.AbstractEventLoop,
    scheduler: DynamicSidecarsScheduler,
    scheduler_data: SchedulerData,
    docker_swarm: None,
    mocked_dynamic_scheduler_events: None,
) -> None:
    await scheduler.add_service(scheduler_data)
    await scheduler.add_service(scheduler_data)


async def test_collition_at_global_level(
    loop: asyncio.AbstractEventLoop,
    scheduler: DynamicSidecarsScheduler,
    scheduler_data: SchedulerData,
    docker_swarm: None,
    mocked_dynamic_scheduler_events: None,
) -> None:
    # pylint: disable=protected-access
    scheduler._inverse_search_mapping[scheduler_data.node_uuid] = "mock_service_name"
    with pytest.raises(DynamicSidecarError) as execinfo:
        await scheduler.add_service(scheduler_data)
    assert "node_uuids at a global level collided." in str(execinfo.value)


async def test_no_service_name(
    loop: asyncio.AbstractEventLoop,
    scheduler: DynamicSidecarsScheduler,
    scheduler_data: SchedulerData,
    docker_swarm: None,
    mocked_dynamic_scheduler_events: None,
) -> None:
    scheduler_data.service_name = ""
    with pytest.raises(DynamicSidecarError) as execinfo:
        await scheduler.add_service(scheduler_data)
    assert "a service with no name is not valid. Invalid usage." == str(execinfo.value)


async def test_remove_missing_no_error(
    loop: asyncio.AbstractEventLoop,
    scheduler: DynamicSidecarsScheduler,
    scheduler_data: SchedulerData,
    docker_swarm: None,
    mocked_dynamic_scheduler_events: None,
) -> None:
    with pytest.raises(DynamicSidecarNotFoundError) as execinfo:
        await scheduler.mark_service_for_removal(scheduler_data.node_uuid, True)
    assert f"node {scheduler_data.node_uuid} not found" == str(execinfo.value)


async def test_get_stack_status(
    loop: asyncio.AbstractEventLoop,
    ensure_scheduler_runs_once: Callable,
    scheduler: DynamicSidecarsScheduler,
    scheduler_data: SchedulerData,
    docker_swarm: None,
    mocked_dynamic_scheduler_events: None,
) -> None:
    await ensure_scheduler_runs_once()

    await scheduler.add_service(scheduler_data)

    stack_status = await scheduler.get_stack_status(scheduler_data.node_uuid)
    assert stack_status == RunningDynamicServiceDetails.from_scheduler_data(
        node_uuid=scheduler_data.node_uuid,
        scheduler_data=scheduler_data,
        service_state=ServiceState.PENDING,
        service_message="",
    )


async def test_get_stack_status_missing(
    loop: asyncio.AbstractEventLoop,
    scheduler: DynamicSidecarsScheduler,
    scheduler_data: SchedulerData,
    docker_swarm: None,
    mocked_dynamic_scheduler_events: None,
) -> None:
    with pytest.raises(DynamicSidecarNotFoundError) as execinfo:
        await scheduler.get_stack_status(scheduler_data.node_uuid)
    assert f"node {scheduler_data.node_uuid} not found" in str(execinfo)


async def test_get_stack_status_failing_sidecar(
    loop: asyncio.AbstractEventLoop,
    scheduler: DynamicSidecarsScheduler,
    scheduler_data: SchedulerData,
    docker_swarm: None,
    mocked_dynamic_scheduler_events: None,
) -> None:
    failing_message = "some_failing_message"
    scheduler_data.dynamic_sidecar.status.update_failing_status(failing_message)

    await scheduler.add_service(scheduler_data)

    stack_status = await scheduler.get_stack_status(scheduler_data.node_uuid)
    assert stack_status == RunningDynamicServiceDetails.from_scheduler_data(
        node_uuid=scheduler_data.node_uuid,
        scheduler_data=scheduler_data,
        service_state=ServiceState.FAILED,
        service_message=failing_message,
    )


async def test_get_stack_status_report_missing_statuses(
    loop: asyncio.AbstractEventLoop,
    scheduler: DynamicSidecarsScheduler,
    scheduler_data: SchedulerData,
    mock_service_running: AsyncMock,
    docker_swarm: None,
    mocked_dynamic_scheduler_events: None,
) -> None:
    async with _assert_get_dynamic_services_mocked(
        scheduler,
        scheduler_data,
        mock_service_running,
        expected_response=httpx.HTTPError("Mock raised error"),
    ) as stack_status:
        assert stack_status == RunningDynamicServiceDetails.from_scheduler_data(
            node_uuid=scheduler_data.node_uuid,
            scheduler_data=scheduler_data,
            service_state=ServiceState.STARTING,
            service_message="There was an error while trying to fetch the stautes form the contianers",
        )


async def test_get_stack_status_containers_are_starting(
    loop: asyncio.AbstractEventLoop,
    scheduler: DynamicSidecarsScheduler,
    scheduler_data: SchedulerData,
    mock_service_running: AsyncMock,
    docker_swarm: None,
    mocked_dynamic_scheduler_events: None,
) -> None:
    async with _assert_get_dynamic_services_mocked(
        scheduler,
        scheduler_data,
        mock_service_running,
        expected_response=httpx.Response(200, json={}),
    ) as stack_status:
        assert stack_status == RunningDynamicServiceDetails.from_scheduler_data(
            node_uuid=scheduler_data.node_uuid,
            scheduler_data=scheduler_data,
            service_state=ServiceState.STARTING,
            service_message="",
        )


async def test_get_stack_status_ok(
    loop: asyncio.AbstractEventLoop,
    scheduler: DynamicSidecarsScheduler,
    scheduler_data: SchedulerData,
    mock_service_running: AsyncMock,
    docker_swarm: None,
    mocked_dynamic_scheduler_events: None,
) -> None:
    async with _assert_get_dynamic_services_mocked(
        scheduler,
        scheduler_data,
        mock_service_running,
        expected_response=httpx.Response(
            200, json={"fake_entry": {"Status": "running"}}
        ),
    ) as stack_status:
        assert stack_status == RunningDynamicServiceDetails.from_scheduler_data(
            node_uuid=scheduler_data.node_uuid,
            scheduler_data=scheduler_data,
            service_state=ServiceState.RUNNING,
            service_message="",
        )


def test_module_setup(
    loop: asyncio.AbstractEventLoop,
    dynamic_sidecar_settings: AppSettings,
    docker_swarm: None,
) -> None:
    app = FastAPI()
    app.state.settings = dynamic_sidecar_settings
    module_setup.setup(app)
    with TestClient(app):
        pass
