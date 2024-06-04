# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

import json
import re
from collections.abc import AsyncIterable
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
    set_request_as_running,
)
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


# create service pattern for start & stop with the appropriate type of message types
# including idle and the ones for legacy services


class _StatusResponseTimeline:
    # TODO: use to generate a future timeline of responses in order to properly test
    # how the status wil behave with time
    pass


@pytest.fixture
async def mock_director_v2_status(
    app: FastAPI,
    service_status: NodeGet | DynamicServiceGet | NodeGetIdle,
) -> AsyncIterable[None]:
    def _side_effect_node_status_response(request: Request) -> Response:
        node_id = NodeID(f"{request.url}".split("/")[-1])
        print("<<<<<<<<", node_id, request.url)

        # fetch `node_id` from request and then compose sequence of events which which it should respond
        if isinstance(service_status, NodeGet):
            return Response(
                status.HTTP_200_OK,
                text=json.dumps(jsonable_encoder({"data": service_status.dict()})),
            )
        if isinstance(service_status, DynamicServiceGet):
            return Response(status.HTTP_200_OK, text=service_status.json())
        if isinstance(service_status, NodeGetIdle):
            return Response(status.HTTP_404_NOT_FOUND)

    # Not moced http://director-v2:8000/v2/dynamic_services/87a2a7c6-7166-4ffe-8a03-e4e947753ed3

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
        "on_result",
        "run",
        "on_finished_with_error",
    ):
        mock_method = mocker.AsyncMock(wraps=getattr(DeferredGetStatus, method_name))
        mocker.patch.object(DeferredGetStatus, method_name, mock_method)
        results[method_name] = mock_method

    return results


async def _wait_for_result(
    deferred_status_spies: dict[str, AsyncMock], *, key: str, count: NonNegativeInt
) -> None:
    async for attempt in AsyncRetrying(
        reraise=True,
        stop=stop_after_delay(5),
        wait=wait_fixed(0.01),
        retry=retry_if_exception_type(AssertionError),
    ):
        with attempt:
            assert deferred_status_spies[key].call_count == count


@pytest.mark.parametrize(
    "service_status",
    [
        NodeGet.parse_obj(NodeGet.Config.schema_extra["example"]),
        *(
            DynamicServiceGet.parse_obj(x)
            for x in DynamicServiceGet.Config.schema_extra["examples"]
        ),
        NodeGetIdle.parse_obj(NodeGetIdle.Config.schema_extra["example"]),
    ],
)
async def test_basic_examples(
    deferred_status_spies: dict[str, AsyncMock],
    app: FastAPI,
    monitor: Monitor,
    service_status: NodeGet | DynamicServiceGet | NodeGetIdle,
):
    mode_id = uuid4()
    await set_request_as_running(app, mode_id)

    # ADD some service to monitor, then mock the API to director-v2 to returns different
    # statuses based on the times when it is called

    await monitor._worker_start_get_status_requests()

    await _wait_for_result(deferred_status_spies, key="run", count=1)
    await _wait_for_result(deferred_status_spies, key="on_result", count=1)
    await _wait_for_result(deferred_status_spies, key="on_finished_with_error", count=0)
