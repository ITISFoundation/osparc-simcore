# pylint:disable=redefined-outer-name
# pylint:disable=too-many-positional-arguments
# pylint:disable=unused-argument

import itertools
import json
import re
from collections.abc import AsyncIterable, Callable
from copy import deepcopy
from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
import respx
from fastapi import FastAPI, status
from fastapi.encoders import jsonable_encoder
from httpx import Request, Response
from models_library.api_schemas_directorv2.dynamic_services import DynamicServiceGet
from models_library.api_schemas_dynamic_scheduler.dynamic_services import (
    DynamicServiceStart,
    DynamicServiceStop,
)
from models_library.api_schemas_webserver.projects_nodes import NodeGet, NodeGetIdle
from models_library.projects_nodes_io import NodeID
from pydantic import NonNegativeInt, TypeAdapter
from pytest_mock import MockerFixture
from pytest_simcore.helpers.typing_env import EnvVarsDict
from settings_library.rabbit import RabbitSettings
from settings_library.redis import RedisSettings
from simcore_service_dynamic_scheduler.services.service_tracker import (
    get_all_tracked_services,
    set_request_as_running,
    set_request_as_stopped,
)
from simcore_service_dynamic_scheduler.services.service_tracker._models import (
    SchedulerServiceState,
    TrackedServiceModel,
    UserRequestedState,
)
from simcore_service_dynamic_scheduler.services.status_monitor import _monitor
from simcore_service_dynamic_scheduler.services.status_monitor._deferred_get_status import (
    DeferredGetStatus,
)
from simcore_service_dynamic_scheduler.services.status_monitor._monitor import (
    Monitor,
    _can_be_removed,
)
from simcore_service_dynamic_scheduler.services.status_monitor._setup import get_monitor
from tenacity import AsyncRetrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

pytest_simcore_core_services_selection = [
    "rabbit",
    "redis",
]


@pytest.fixture
def app_environment(
    app_environment: EnvVarsDict,
    rabbit_service: RabbitSettings,
    redis_service: RedisSettings,
    remove_redis_data: None,
) -> EnvVarsDict:
    return app_environment


_DEFAULT_NODE_ID: NodeID = uuid4()


def _add_to_dict(dict_data: dict, entries: list[tuple[str, Any]]) -> None:
    for key, data in entries:
        assert key in dict_data
        dict_data[key] = data


def _get_node_get_with(state: str, node_id: NodeID = _DEFAULT_NODE_ID) -> NodeGet:
    dict_data = deepcopy(NodeGet.model_config["json_schema_extra"]["examples"][1])
    _add_to_dict(
        dict_data,
        [
            ("service_state", state),
            ("service_uuid", f"{node_id}"),
        ],
    )
    return TypeAdapter(NodeGet).validate_python(dict_data)


def _get_dynamic_service_get_legacy_with(
    state: str, node_id: NodeID = _DEFAULT_NODE_ID
) -> DynamicServiceGet:
    dict_data = deepcopy(
        DynamicServiceGet.model_config["json_schema_extra"]["examples"][0]
    )
    _add_to_dict(
        dict_data,
        [
            ("state", state),
            ("uuid", f"{node_id}"),
            ("node_uuid", f"{node_id}"),
        ],
    )
    return TypeAdapter(DynamicServiceGet).validate_python(dict_data)


def _get_dynamic_service_get_new_style_with(
    state: str, node_id: NodeID = _DEFAULT_NODE_ID
) -> DynamicServiceGet:
    dict_data = deepcopy(
        DynamicServiceGet.model_config["json_schema_extra"]["examples"][1]
    )
    _add_to_dict(
        dict_data,
        [
            ("state", state),
            ("uuid", f"{node_id}"),
            ("node_uuid", f"{node_id}"),
        ],
    )
    return TypeAdapter(DynamicServiceGet).validate_python(dict_data)


def _get_node_get_idle(node_id: NodeID = _DEFAULT_NODE_ID) -> NodeGetIdle:
    dict_data = NodeGetIdle.model_config["json_schema_extra"]["example"]
    _add_to_dict(
        dict_data,
        [
            ("service_uuid", f"{node_id}"),
        ],
    )
    return TypeAdapter(NodeGetIdle).validate_python(dict_data)


class _ResponseTimeline:
    def __init__(
        self, timeline: list[NodeGet | DynamicServiceGet | NodeGetIdle]
    ) -> None:
        self._timeline = timeline

        self._client_access_history: dict[NodeID, NonNegativeInt] = {}

    @property
    def entries(self) -> list[NodeGet | DynamicServiceGet | NodeGetIdle]:
        return self._timeline

    def __len__(self) -> int:
        return len(self._timeline)

    def get_status(self, node_id: NodeID) -> NodeGet | DynamicServiceGet | NodeGetIdle:
        if node_id not in self._client_access_history:
            self._client_access_history[node_id] = 0

        # always return node idle when timeline finished playing
        if self._client_access_history[node_id] >= len(self._timeline):
            return _get_node_get_idle()

        status = self._timeline[self._client_access_history[node_id]]
        self._client_access_history[node_id] += 1
        return status


async def _assert_call_to(
    deferred_status_spies: dict[str, AsyncMock], *, method: str, count: NonNegativeInt
) -> None:
    async for attempt in AsyncRetrying(
        reraise=True,
        stop=stop_after_delay(1),
        wait=wait_fixed(0.01),
        retry=retry_if_exception_type(AssertionError),
    ):
        with attempt:
            call_count = deferred_status_spies[method].call_count
            assert (
                call_count == count
            ), f"Received calls {call_count} != {count} (expected) to '{method}'"


async def _assert_result(
    deferred_status_spies: dict[str, AsyncMock],
    *,
    timeline: list[NodeGet | DynamicServiceGet | NodeGetIdle],
) -> None:
    async for attempt in AsyncRetrying(
        reraise=True,
        stop=stop_after_delay(1),
        wait=wait_fixed(0.01),
        retry=retry_if_exception_type(AssertionError),
    ):
        with attempt:

            assert deferred_status_spies["on_result"].call_count == len(timeline)
            assert [
                x.args[0] for x in deferred_status_spies["on_result"].call_args_list
            ] == timeline


async def _assert_notification_count(
    mock: AsyncMock, expected_count: NonNegativeInt
) -> None:
    async for attempt in AsyncRetrying(
        reraise=True,
        stop=stop_after_delay(1),
        wait=wait_fixed(0.01),
        retry=retry_if_exception_type(AssertionError),
    ):
        with attempt:
            assert mock.call_count == expected_count


@pytest.fixture
async def mock_director_v2_status(
    app: FastAPI, response_timeline: _ResponseTimeline
) -> AsyncIterable[None]:
    def _side_effect_node_status_response(request: Request) -> Response:
        node_id = NodeID(f"{request.url}".split("/")[-1])

        service_status = response_timeline.get_status(node_id)

        if isinstance(service_status, NodeGet):
            return Response(
                status.HTTP_200_OK,
                text=json.dumps(
                    jsonable_encoder({"data": service_status.model_dump()})
                ),
            )
        if isinstance(service_status, DynamicServiceGet):
            return Response(status.HTTP_200_OK, text=service_status.model_dump_json())
        if isinstance(service_status, NodeGetIdle):
            return Response(status.HTTP_404_NOT_FOUND)

        raise TypeError

    with respx.mock(
        base_url=app.state.settings.DYNAMIC_SCHEDULER_DIRECTOR_V2_SETTINGS.api_base_url,
        assert_all_called=False,
        assert_all_mocked=True,
    ) as mock:
        mock.get(re.compile(r"/dynamic_services/([\w-]+)")).mock(
            side_effect=_side_effect_node_status_response
        )
        yield


@pytest.fixture
def monitor(mock_director_v2_status: None, app: FastAPI) -> Monitor:
    return get_monitor(app)


@pytest.fixture
def deferred_status_spies(mocker: MockerFixture) -> dict[str, AsyncMock]:
    results: dict[str, AsyncMock] = {}
    for method_name in (
        "start",
        "on_result",
        "on_created",
        "run",
        "on_finished_with_error",
    ):
        mock_method = mocker.AsyncMock(wraps=getattr(DeferredGetStatus, method_name))
        mocker.patch.object(DeferredGetStatus, method_name, mock_method)
        results[method_name] = mock_method

    return results


@pytest.fixture
def remove_tracked_spy(mocker: MockerFixture) -> AsyncMock:
    mock_method = mocker.AsyncMock(
        wraps=_monitor.service_tracker.remove_tracked_service
    )
    return mocker.patch.object(
        _monitor.service_tracker,
        _monitor.service_tracker.remove_tracked_service.__name__,
        mock_method,
    )


@pytest.fixture
def node_id() -> NodeID:
    return _DEFAULT_NODE_ID


@pytest.fixture
def mocked_notify_frontend(mocker: MockerFixture) -> AsyncMock:
    return mocker.patch(
        "simcore_service_dynamic_scheduler.services.status_monitor._deferred_get_status.notify_service_status_change"
    )


@pytest.fixture
def disable_status_monitor_background_task(mocker: MockerFixture) -> None:
    mocker.patch(
        "simcore_service_dynamic_scheduler.services.status_monitor._monitor.Monitor.setup"
    )


@pytest.mark.parametrize(
    "user_requests_running, response_timeline, expected_notification_count, remove_tracked_count",
    [
        pytest.param(
            True,
            _ResponseTimeline([_get_node_get_with("running")]),
            1,
            0,
            id="requested_running_state_changes_1_no_task_removal",
        ),
        pytest.param(
            True,
            _ResponseTimeline(
                [_get_dynamic_service_get_legacy_with("running") for _ in range(10)]
            ),
            1,
            0,
            id="requested_running_state_changes_1_for_multiple_same_state_no_task_removal",
        ),
        pytest.param(
            True,
            _ResponseTimeline([_get_node_get_idle()]),
            1,
            0,
            id="requested_running_state_idle_no_removal",
        ),
        pytest.param(
            False,
            _ResponseTimeline([_get_node_get_idle()]),
            1,
            1,
            id="requested_stopped_state_idle_is_removed",
        ),
        pytest.param(
            True,
            _ResponseTimeline(
                [
                    *[_get_node_get_idle() for _ in range(10)],
                    _get_dynamic_service_get_new_style_with("pending"),
                    _get_dynamic_service_get_new_style_with("pulling"),
                    *[
                        _get_dynamic_service_get_new_style_with("starting")
                        for _ in range(10)
                    ],
                    _get_dynamic_service_get_new_style_with("running"),
                    _get_dynamic_service_get_new_style_with("stopping"),
                    _get_dynamic_service_get_new_style_with("complete"),
                    _get_node_get_idle(),
                ]
            ),
            8,
            0,
            id="requested_running_state_changes_8_no_removal",
        ),
        pytest.param(
            False,
            _ResponseTimeline(
                [
                    _get_dynamic_service_get_new_style_with("pending"),
                    _get_dynamic_service_get_new_style_with("pulling"),
                    *[
                        _get_dynamic_service_get_new_style_with("starting")
                        for _ in range(10)
                    ],
                    _get_dynamic_service_get_new_style_with("running"),
                    _get_dynamic_service_get_new_style_with("stopping"),
                    _get_dynamic_service_get_new_style_with("complete"),
                    _get_node_get_idle(),
                ]
            ),
            7,
            1,
            id="requested_stopped_state_changes_7_is_removed",
        ),
    ],
)
async def test_expected_calls_to_notify_frontend(  # pylint:disable=too-many-arguments
    disable_status_monitor_background_task: None,
    mocked_notify_frontend: AsyncMock,
    deferred_status_spies: dict[str, AsyncMock],
    remove_tracked_spy: AsyncMock,
    app: FastAPI,
    monitor: Monitor,
    node_id: NodeID,
    user_requests_running: bool,
    response_timeline: _ResponseTimeline,
    expected_notification_count: NonNegativeInt,
    remove_tracked_count: NonNegativeInt,
    get_dynamic_service_start: Callable[[NodeID], DynamicServiceStart],
    get_dynamic_service_stop: Callable[[NodeID], DynamicServiceStop],
):
    assert await get_all_tracked_services(app) == {}

    if user_requests_running:
        await set_request_as_running(app, get_dynamic_service_start(node_id))
    else:
        await set_request_as_stopped(app, get_dynamic_service_stop(node_id))

    entries_in_timeline = len(response_timeline)

    for i in range(entries_in_timeline):
        async for attempt in AsyncRetrying(
            reraise=True, stop=stop_after_delay(10), wait=wait_fixed(0.1)
        ):
            with attempt:
                # pylint:disable=protected-access
                await monitor._worker_start_get_status_requests()  # noqa: SLF001
                for method in ("start", "on_created", "on_result"):
                    await _assert_call_to(
                        deferred_status_spies, method=method, count=i + 1
                    )

    await _assert_call_to(
        deferred_status_spies, method="run", count=entries_in_timeline
    )
    await _assert_call_to(
        deferred_status_spies, method="on_finished_with_error", count=0
    )

    await _assert_result(deferred_status_spies, timeline=response_timeline.entries)

    await _assert_notification_count(
        mocked_notify_frontend, expected_notification_count
    )

    async for attempt in AsyncRetrying(
        reraise=True, stop=stop_after_delay(1), wait=wait_fixed(0.1)
    ):
        with attempt:
            # pylint:disable=protected-access
            await monitor._worker_start_get_status_requests()  # noqa: SLF001
            assert remove_tracked_spy.call_count == remove_tracked_count


@pytest.fixture
def mock_tracker_remove_after_idle_for(mocker: MockerFixture) -> None:
    mocker.patch(
        "simcore_service_dynamic_scheduler.services.status_monitor._monitor._REMOVE_AFTER_IDLE_FOR",
        timedelta(seconds=0.1),
    )


@pytest.mark.parametrize(
    "requested_state, current_state, immediate_can_be_removed, can_be_removed",
    [
        pytest.param(
            UserRequestedState.RUNNING,
            SchedulerServiceState.IDLE,
            False,
            True,
            id="can_remove_after_an_interval",
        ),
        pytest.param(
            UserRequestedState.STOPPED,
            SchedulerServiceState.IDLE,
            True,
            True,
            id="can_remove_no_interval",
        ),
        *[
            pytest.param(
                requested_state,
                service_state,
                False,
                False,
                id=f"not_removed_{requested_state=}_{service_state=}",
            )
            for requested_state, service_state in itertools.product(
                set(UserRequestedState),
                {x for x in SchedulerServiceState if x != SchedulerServiceState.IDLE},
            )
        ],
    ],
)
async def test__can_be_removed(
    mock_tracker_remove_after_idle_for: None,
    requested_state: UserRequestedState,
    current_state: SchedulerServiceState,
    immediate_can_be_removed: bool,
    can_be_removed: bool,
):
    model = TrackedServiceModel(
        dynamic_service_start=None,
        user_id=None,
        project_id=None,
        requested_state=requested_state,
    )

    # This also triggers the setter and updates the last state change timer
    model.current_state = current_state

    assert _can_be_removed(model) is immediate_can_be_removed

    async for attempt in AsyncRetrying(
        wait=wait_fixed(0.1),
        stop=stop_after_delay(2),
        reraise=True,
        retry=retry_if_exception_type(AssertionError),
    ):
        with attempt:
            assert _can_be_removed(model) is can_be_removed
