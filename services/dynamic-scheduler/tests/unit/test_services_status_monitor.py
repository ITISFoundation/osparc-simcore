# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

import json
import re
from collections.abc import AsyncIterable
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
from models_library.api_schemas_webserver.projects_nodes import NodeGet, NodeGetIdle
from models_library.projects_nodes_io import NodeID
from pydantic import NonNegativeInt
from pytest_mock import MockerFixture
from pytest_simcore.helpers.typing_env import EnvVarsDict
from settings_library.rabbit import RabbitSettings
from settings_library.redis import RedisSettings
from simcore_service_dynamic_scheduler.services.service_tracker import (
    _api,
    set_request_as_running,
)
from simcore_service_dynamic_scheduler.services.status_monitor import _monitor
from simcore_service_dynamic_scheduler.services.status_monitor._deferred_get_status import (
    DeferredGetStatus,
)
from simcore_service_dynamic_scheduler.services.status_monitor._monitor import Monitor
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
    dict_data = deepcopy(NodeGet.Config.schema_extra["example"])
    _add_to_dict(
        dict_data,
        [
            ("service_state", state),
            ("service_uuid", f"{node_id}"),
        ],
    )
    return NodeGet.parse_obj(dict_data)


def __get_dynamic_service_get_legacy_with(
    state: str, node_id: NodeID = _DEFAULT_NODE_ID
) -> DynamicServiceGet:
    dict_data = deepcopy(DynamicServiceGet.Config.schema_extra["examples"][0])
    _add_to_dict(
        dict_data,
        [
            ("state", state),
            ("uuid", f"{node_id}"),
            ("node_uuid", f"{node_id}"),
        ],
    )
    return DynamicServiceGet.parse_obj(dict_data)


def __get_dynamic_service_get_new_style_with(
    state: str, node_id: NodeID = _DEFAULT_NODE_ID
) -> DynamicServiceGet:
    dict_data = deepcopy(DynamicServiceGet.Config.schema_extra["examples"][1])
    _add_to_dict(
        dict_data,
        [
            ("state", state),
            ("uuid", f"{node_id}"),
            ("node_uuid", f"{node_id}"),
        ],
    )
    return DynamicServiceGet.parse_obj(dict_data)


def __get_node_get_idle(node_id: NodeID = _DEFAULT_NODE_ID) -> NodeGetIdle:
    dict_data = NodeGetIdle.Config.schema_extra["example"]
    _add_to_dict(
        dict_data,
        [
            ("service_uuid", f"{node_id}"),
        ],
    )
    return NodeGetIdle.parse_obj(dict_data)


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
            return __get_node_get_idle()

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
                text=json.dumps(jsonable_encoder({"data": service_status.dict()})),
            )
        if isinstance(service_status, DynamicServiceGet):
            return Response(status.HTTP_200_OK, text=service_status.json())
        if isinstance(service_status, NodeGetIdle):
            return Response(status.HTTP_404_NOT_FOUND)

        raise TypeError()

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
def node_id() -> NodeID:
    return _DEFAULT_NODE_ID


@pytest.fixture
def mocked_notify_frontend(mocker: MockerFixture) -> AsyncMock:
    return mocker.patch(
        "simcore_service_dynamic_scheduler.services.status_monitor._deferred_get_status.notify_frontend"
    )


@pytest.fixture
def mock_poll_rate_intervals(mocker: MockerFixture) -> None:
    mocker.patch.object(_api, "_LOW_RATE_POLL_INTERVAL", timedelta(seconds=0.1))
    mocker.patch.object(_api, "NORMAL_RATE_POLL_INTERVAL", timedelta(seconds=0.2))
    mocker.patch.object(_monitor, "NORMAL_RATE_POLL_INTERVAL", timedelta(seconds=0.2))


@pytest.mark.parametrize(
    "response_timeline, expected_notification_count",
    [
        # TODO: below
        # create service pattern for start & stop with the appropriate type of message types
        # including idle and the ones for legacy services
        (_ResponseTimeline([_get_node_get_with("running")]), 1),
        (
            _ResponseTimeline(
                [__get_dynamic_service_get_legacy_with("running") for _ in range(10)]
            ),
            1,
        ),
        (_ResponseTimeline([__get_dynamic_service_get_new_style_with("running")]), 1),
        (_ResponseTimeline([__get_node_get_idle()]), 1),
    ],
)
async def test_expected_calls_to_notify_frontend(
    mock_poll_rate_intervals: None,
    mocked_notify_frontend: AsyncMock,
    deferred_status_spies: dict[str, AsyncMock],
    app: FastAPI,
    monitor: Monitor,
    node_id: NodeID,
    response_timeline: _ResponseTimeline,
    expected_notification_count: NonNegativeInt,
):
    await set_request_as_running(app, node_id)

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
