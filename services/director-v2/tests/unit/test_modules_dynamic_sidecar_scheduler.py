# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=protected-access


import logging
import re
import urllib.parse
from collections.abc import AsyncGenerator, Awaitable, Callable, Iterator
from contextlib import asynccontextmanager, contextmanager
from typing import Final
from unittest.mock import AsyncMock

import pytest
import respx
from faker import Faker
from fastapi import FastAPI
from models_library.api_schemas_directorv2.dynamic_services_service import (
    RunningDynamicServiceDetails,
)
from models_library.service_settings_labels import SimcoreServiceLabels
from models_library.services_enums import ServiceState
from models_library.wallets import WalletID
from pydantic import NonNegativeFloat
from pytest_mock.plugin import MockerFixture
from pytest_simcore.helpers.typing_env import EnvVarsDict
from respx.router import MockRouter
from simcore_service_director_v2.core.settings import AppSettings
from simcore_service_director_v2.models.dynamic_services_scheduler import (
    DockerContainerInspect,
    DynamicSidecarStatus,
    SchedulerData,
    ServiceName,
)
from simcore_service_director_v2.modules.dynamic_sidecar.errors import (
    DynamicSidecarError,
    DynamicSidecarNotFoundError,
)
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler import (
    DynamicSidecarsScheduler,
)
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._core._events import (
    DynamicSchedulerEvent,
)
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._core._observer import (
    _apply_observation_cycle,
)
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._core._scheduler import (
    Scheduler,
)
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._core._scheduler_utils import (
    create_model_from_scheduler_data,
)

# running scheduler at a hight rate to stress out the system
# and ensure faster tests
_TEST_SCHEDULER_INTERVAL_SECONDS: Final[NonNegativeFloat] = 0.1

log = logging.getLogger(__name__)


pytest_simcore_core_services_selection = ["postgres"]
pytest_simcore_ops_services_selection = ["adminer"]


def get_url(dynamic_sidecar_endpoint: str, postfix: str) -> str:
    return f"{dynamic_sidecar_endpoint}{postfix}"


# UTILS
@contextmanager
def _mock_containers_docker_status(
    scheduler_data: SchedulerData,
) -> Iterator[MockRouter]:
    service_endpoint = scheduler_data.endpoint
    with respx.mock as mock:
        mock.get(
            re.compile(
                rf"^http://{scheduler_data.service_name}:{scheduler_data.port}/health"
            ),
            name="health",
        ).respond(json={"is_healthy": True, "error": None})
        mock.post(
            get_url(service_endpoint, "/v1/containers:down"),
            name="begin_service_destruction",
        ).respond(text="")

        yield mock


@asynccontextmanager
async def _assert_get_dynamic_services_mocked(
    scheduler: DynamicSidecarsScheduler,
    scheduler_data: SchedulerData,
    mock_service_running: AsyncMock,
    expected_status: str,
) -> AsyncGenerator[RunningDynamicServiceDetails, None]:
    with _mock_containers_docker_status(scheduler_data):
        await scheduler.scheduler.add_service_from_scheduler_data(scheduler_data)
        # put mocked data
        scheduler_data.dynamic_sidecar.containers_inspect = [
            DockerContainerInspect.from_container(
                {"State": {"Status": expected_status}, "Name": "", "Id": ""}
            )
        ]

        stack_status = await scheduler.get_stack_status(scheduler_data.node_uuid)
        assert mock_service_running.called

        yield stack_status

        await scheduler.mark_service_for_removal(
            scheduler_data.node_uuid, can_save=True
        )
        assert (
            scheduler_data.service_name
            in scheduler.scheduler._to_observe  # noqa: SLF001
        )
        await scheduler.scheduler.remove_service_from_observation(
            scheduler_data.node_uuid
        )
        assert (
            scheduler_data.service_name
            not in scheduler.scheduler._to_observe  # noqa: SLF001
        )


@pytest.fixture
def mock_env(
    mock_exclusive: None,
    disable_postgres: None,
    disable_rabbitmq: None,
    mock_env: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
    simcore_services_network_name: str,
    mock_docker_api: None,
    faker: Faker,
) -> None:
    monkeypatch.setenv("SIMCORE_SERVICES_NETWORK_NAME", simcore_services_network_name)
    monkeypatch.setenv("DIRECTOR_HOST", "mocked_out")
    monkeypatch.setenv(
        "DIRECTOR_V2_DYNAMIC_SCHEDULER_INTERVAL", f"{_TEST_SCHEDULER_INTERVAL_SECONDS}"
    )
    monkeypatch.setenv("DIRECTOR_V2_DYNAMIC_SCHEDULER_ENABLED", "true")
    monkeypatch.setenv("S3_ENDPOINT", faker.url())
    monkeypatch.setenv("S3_ACCESS_KEY", faker.pystr())
    monkeypatch.setenv("S3_REGION", faker.pystr())
    monkeypatch.setenv("S3_SECRET_KEY", faker.pystr())
    monkeypatch.setenv("S3_BUCKET_NAME", faker.pystr())


@pytest.fixture
def mocked_director_v0(
    minimal_config: AppSettings, scheduler_data: SchedulerData
) -> Iterator[MockRouter]:
    endpoint = minimal_config.DIRECTOR_V0.endpoint

    with respx.mock as mock:
        mock.get(
            re.compile(
                rf"^{endpoint}/services/{urllib.parse.quote_plus(scheduler_data.key)}/{scheduler_data.version}/labels"
            ),
            name="service labels",
        ).respond(
            json={
                "data": SimcoreServiceLabels.model_config["json_schema_extra"][
                    "examples"
                ][0]
            }
        )
        yield mock


@pytest.fixture
def mocked_dynamic_scheduler_events(mocker: MockerFixture) -> None:
    class AlwaysTriggersDynamicSchedulerEvent(DynamicSchedulerEvent):
        @classmethod
        async def will_trigger(
            cls,
            app: FastAPI,  # noqa: ARG003
            scheduler_data: SchedulerData,  # noqa: ARG003
        ) -> bool:
            return True

        @classmethod
        async def action(
            cls,
            app: FastAPI,  # noqa: ARG003
            scheduler_data: SchedulerData,  # noqa: ARG003
        ) -> None:
            message = f"{cls.__name__} action triggered"
            log.warning(message)

    # replace REGISTERED EVENTS
    mocker.patch(
        "simcore_service_director_v2.modules.dynamic_sidecar.scheduler._core._observer.REGISTERED_EVENTS",
        [AlwaysTriggersDynamicSchedulerEvent],
    )


@pytest.fixture
def scheduler(minimal_app: FastAPI) -> DynamicSidecarsScheduler:
    return minimal_app.state.dynamic_sidecar_scheduler


@pytest.fixture
def scheduler_data(scheduler_data_from_http_request: SchedulerData) -> SchedulerData:
    return scheduler_data_from_http_request


@pytest.fixture
def mocked_api_client(scheduler_data: SchedulerData) -> Iterator[MockRouter]:
    service_endpoint = scheduler_data.endpoint
    with respx.mock as mock:
        mock.get(get_url(service_endpoint, "/health"), name="is_healthy").respond(
            json={"is_healthy": True}
        )
        mock.post(
            get_url(service_endpoint, "/v1/containers:down"),
            name="begin_service_destruction",
        ).respond(text="")

        yield mock


@pytest.fixture
def mock_service_running(mock_docker_api, mocker: MockerFixture) -> AsyncMock:
    return mocker.patch(
        "simcore_service_director_v2.modules.dynamic_sidecar.scheduler._core._scheduler_utils.get_dynamic_sidecar_state",
        return_value=(ServiceState.RUNNING, ""),
    )


@pytest.fixture
def mock_update_label(mocker: MockerFixture) -> None:
    mocker.patch(
        "simcore_service_director_v2.modules.dynamic_sidecar.scheduler._core._scheduler.update_scheduler_data_label",
        return_value=None,
    )


@pytest.fixture
def disabled_scheduler_background_task(mocker: MockerFixture):
    mocker.patch(
        "simcore_service_director_v2.modules.dynamic_sidecar.scheduler._task.DynamicSidecarsScheduler.start",
        autospec=True,
    )


@pytest.fixture
async def manually_trigger_scheduler(
    scheduler: DynamicSidecarsScheduler, scheduler_data: SchedulerData
) -> Callable[[], Awaitable[None]]:
    async def _coroutine() -> None:
        await _apply_observation_cycle(scheduler, scheduler_data)

    return _coroutine


@pytest.mark.parametrize("with_observation_cycle", [True, False])
async def test_scheduler_add_remove(
    disabled_scheduler_background_task: None,
    manually_trigger_scheduler: Callable[[], Awaitable[None]],
    scheduler: DynamicSidecarsScheduler,
    scheduler_data: SchedulerData,
    mocked_api_client: MockRouter,
    docker_swarm: None,
    mocked_dynamic_scheduler_events: None,
    mock_update_label: None,
    with_observation_cycle: bool,
) -> None:
    await scheduler.scheduler.add_service_from_scheduler_data(scheduler_data)
    if with_observation_cycle:
        await manually_trigger_scheduler()

    await scheduler.mark_service_for_removal(scheduler_data.node_uuid, can_save=True)
    if with_observation_cycle:
        await manually_trigger_scheduler()

    assert (
        scheduler_data.service_name in scheduler.scheduler._to_observe  # noqa: SLF001
    )

    await scheduler.scheduler.remove_service_from_observation(scheduler_data.node_uuid)
    if with_observation_cycle:
        await manually_trigger_scheduler()
    assert (
        scheduler_data.service_name
        not in scheduler.scheduler._to_observe  # noqa: SLF001
    )


@pytest.mark.flaky(max_runs=3)
async def test_scheduler_removes_partially_started_services(
    disabled_scheduler_background_task: None,
    manually_trigger_scheduler: Callable[[], Awaitable[None]],
    scheduler: DynamicSidecarsScheduler,
    scheduler_data: SchedulerData,
    mocked_dynamic_scheduler_events: None,
    mock_docker_api: None,
) -> None:
    await manually_trigger_scheduler()
    await scheduler.scheduler.add_service_from_scheduler_data(scheduler_data)

    scheduler_data.dynamic_sidecar.were_containers_created = True
    await manually_trigger_scheduler()


async def test_scheduler_is_failing(
    disabled_scheduler_background_task: None,
    manually_trigger_scheduler: Callable[[], Awaitable[None]],
    scheduler: DynamicSidecarsScheduler,
    scheduler_data: SchedulerData,
    mocked_dynamic_scheduler_events: None,
) -> None:
    await manually_trigger_scheduler()
    await scheduler.scheduler.add_service_from_scheduler_data(scheduler_data)

    scheduler_data.dynamic_sidecar.status.current = DynamicSidecarStatus.FAILING
    await manually_trigger_scheduler()


async def test_scheduler_health_timing_out(
    disabled_scheduler_background_task: None,
    manually_trigger_scheduler: Callable[[], Awaitable[None]],
    scheduler: DynamicSidecarsScheduler,
    scheduler_data: SchedulerData,
    mocked_dynamic_scheduler_events: None,
):
    await manually_trigger_scheduler()
    await scheduler.scheduler.add_service_from_scheduler_data(scheduler_data)
    await manually_trigger_scheduler()

    assert scheduler_data.dynamic_sidecar.is_ready is False


async def test_adding_service_two_times_does_not_raise(
    scheduler: DynamicSidecarsScheduler,
    scheduler_data: SchedulerData,
    mocked_dynamic_scheduler_events: None,
):
    await scheduler.scheduler.add_service_from_scheduler_data(scheduler_data)
    assert (
        scheduler_data.service_name in scheduler.scheduler._to_observe  # noqa: SLF001
    )
    await scheduler.scheduler.add_service_from_scheduler_data(scheduler_data)


async def test_collition_at_global_level_raises(
    scheduler: DynamicSidecarsScheduler,
    scheduler_data: SchedulerData,
    mocked_dynamic_scheduler_events: None,
    mock_docker_api: None,
):
    scheduler.scheduler._inverse_search_mapping[  # noqa: SLF001
        scheduler_data.node_uuid
    ] = ServiceName("mock_service_name")
    with pytest.raises(DynamicSidecarError) as execinfo:
        await scheduler.scheduler.add_service_from_scheduler_data(scheduler_data)
    assert "collide" in str(execinfo.value)


async def test_remove_missing_no_error(
    scheduler: DynamicSidecarsScheduler,
    scheduler_data: SchedulerData,
    mocked_dynamic_scheduler_events: None,
    mock_docker_api: None,
) -> None:
    with pytest.raises(DynamicSidecarNotFoundError) as execinfo:
        await scheduler.mark_service_for_removal(
            scheduler_data.node_uuid, can_save=True
        )
    assert "not found" in str(execinfo.value)


async def test_get_stack_status(
    disabled_scheduler_background_task: None,
    manually_trigger_scheduler: Callable[[], Awaitable[None]],
    scheduler: DynamicSidecarsScheduler,
    scheduler_data: SchedulerData,
    mocked_dynamic_scheduler_events: None,
    mock_docker_api: None,
) -> None:
    await manually_trigger_scheduler()
    await scheduler.scheduler.add_service_from_scheduler_data(scheduler_data)

    stack_status = await scheduler.get_stack_status(scheduler_data.node_uuid)
    assert stack_status == create_model_from_scheduler_data(
        node_uuid=scheduler_data.node_uuid,
        scheduler_data=scheduler_data,
        service_state=ServiceState.PENDING,
        service_message="",
    )


async def test_get_stack_status_missing(
    scheduler: DynamicSidecarsScheduler,
    scheduler_data: SchedulerData,
    mocked_dynamic_scheduler_events: None,
    mock_docker_api: None,
) -> None:
    with pytest.raises(
        DynamicSidecarNotFoundError, match=rf"{scheduler_data.node_uuid} not found"
    ):
        await scheduler.get_stack_status(scheduler_data.node_uuid)


async def test_get_stack_status_failing_sidecar(
    scheduler: DynamicSidecarsScheduler,
    scheduler_data: SchedulerData,
    mocked_dynamic_scheduler_events: None,
    mock_docker_api: None,
) -> None:
    failing_message = "some_failing_message"
    scheduler_data.dynamic_sidecar.status.update_failing_status(failing_message)

    await scheduler.scheduler.add_service_from_scheduler_data(scheduler_data)

    stack_status = await scheduler.get_stack_status(scheduler_data.node_uuid)
    assert stack_status == create_model_from_scheduler_data(
        node_uuid=scheduler_data.node_uuid,
        scheduler_data=scheduler_data,
        service_state=ServiceState.FAILED,
        service_message=failing_message,
    )


async def test_get_stack_status_containers_are_starting(
    scheduler: DynamicSidecarsScheduler,
    scheduler_data: SchedulerData,
    mock_service_running: AsyncMock,
    mocked_dynamic_scheduler_events: None,
    mock_update_label: None,
    mock_docker_api: None,
) -> None:
    async with _assert_get_dynamic_services_mocked(
        scheduler, scheduler_data, mock_service_running, expected_status="created"
    ) as stack_status:
        assert stack_status == create_model_from_scheduler_data(
            node_uuid=scheduler_data.node_uuid,
            scheduler_data=scheduler_data,
            service_state=ServiceState.STARTING,
            service_message="",
        )


async def test_get_stack_status_ok(
    scheduler: DynamicSidecarsScheduler,
    scheduler_data: SchedulerData,
    mock_service_running: AsyncMock,
    mocked_dynamic_scheduler_events: None,
    mock_update_label: None,
    mock_docker_api: None,
) -> None:
    async with _assert_get_dynamic_services_mocked(
        scheduler, scheduler_data, mock_service_running, expected_status="running"
    ) as stack_status:
        assert stack_status == create_model_from_scheduler_data(
            node_uuid=scheduler_data.node_uuid,
            scheduler_data=scheduler_data,
            service_state=ServiceState.RUNNING,
            service_message="",
        )


@pytest.fixture
def mocked_app() -> AsyncMock:
    return AsyncMock()


@pytest.mark.parametrize("missing_to_observe_entry", [True, False])
async def test_regression_remove_service_from_observation(
    mocked_app: AsyncMock,
    faker: Faker,
    caplog_debug_level: pytest.LogCaptureFixture,
    missing_to_observe_entry: bool,
):
    scheduler = Scheduler(mocked_app)

    # emulate service was previously added
    node_uuid = faker.uuid4(cast_to=None)
    service_name = ServiceName(f"service_{node_uuid}")
    scheduler._inverse_search_mapping[node_uuid] = service_name  # noqa: SLF001
    if not missing_to_observe_entry:
        scheduler._to_observe[service_name] = AsyncMock()  # noqa: SLF001

    await scheduler.remove_service_from_observation(node_uuid)
    # check log message
    assert f"Removed service '{service_name}' from scheduler" in caplog_debug_level.text

    if missing_to_observe_entry:
        assert f"Unexpected: '{service_name}' not found in" in caplog_debug_level.text


@pytest.mark.parametrize("call_count", [1, 10])
async def test_mark_all_services_in_wallet_for_removal(
    disabled_scheduler_background_task: None,
    scheduler: DynamicSidecarsScheduler,
    scheduler_data: SchedulerData,
    mocked_dynamic_scheduler_events: None,
    faker: Faker,
    call_count: int,
) -> None:
    for wallet_id in [WalletID(1), WalletID(2)]:
        for _ in range(2):
            new_scheduler_data = scheduler_data.model_copy(deep=True)
            new_scheduler_data.node_uuid = faker.uuid4(cast_to=None)
            new_scheduler_data.service_name = ServiceName(
                f"fake_{new_scheduler_data.node_uuid}"
            )
            assert new_scheduler_data.wallet_info
            new_scheduler_data.wallet_info.wallet_id = wallet_id

            await scheduler.scheduler.add_service_from_scheduler_data(
                new_scheduler_data
            )

    assert len(scheduler.scheduler._to_observe) == 4  # noqa: SLF001
    # pylint: disable=redefined-argument-from-local
    for scheduler_data in scheduler.scheduler._to_observe.values():  # noqa: SLF001
        assert scheduler_data.dynamic_sidecar.service_removal_state.can_remove is False

    for _ in range(call_count):
        await scheduler.scheduler.mark_all_services_in_wallet_for_removal(
            wallet_id=WalletID(1)
        )

    for scheduler_data in scheduler.scheduler._to_observe.values():  # noqa: SLF001
        assert scheduler_data.wallet_info
        wallet_id = scheduler_data.wallet_info.wallet_id
        can_remove = scheduler_data.dynamic_sidecar.service_removal_state.can_remove
        match wallet_id:
            case 1:
                assert can_remove is True
            case 2:
                assert can_remove is False
            case _:
                pytest.fail("unexpected case")
