# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=no-value-for-parameter
# pylint:disable=too-many-arguments

import json
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from typing import Any
from unittest import mock

import pytest
from aiohttp.test_utils import TestClient
from faker import Faker
from models_library.projects import ProjectAtDB
from pytest_mock.plugin import MockerFixture
from pytest_simcore.helpers.webserver_login import UserInfoDict
from simcore_postgres_database.models.comp_pipeline import StateType
from simcore_postgres_database.models.comp_tasks import NodeClass, comp_tasks
from simcore_postgres_database.models.users import UserRole
from simcore_service_webserver.db_listener._db_comp_tasks_listening_task import (
    create_comp_tasks_listening_task,
)
from sqlalchemy.ext.asyncio import AsyncEngine
from tenacity.asyncio import AsyncRetrying
from tenacity.before_sleep import before_sleep_log
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

logger = logging.getLogger(__name__)


@pytest.fixture
async def mock_project_subsystem(mocker: MockerFixture) -> dict[str, mock.Mock]:
    mocked_project_calls = {}

    mocked_project_calls["update_node_outputs"] = mocker.patch(
        "simcore_service_webserver.db_listener._db_comp_tasks_listening_task.update_node_outputs",
        return_value="",
    )

    mocked_project_calls["_update_project_state.update_project_node_state"] = (
        mocker.patch(
            "simcore_service_webserver.projects._projects_service.update_project_node_state",
            autospec=True,
        )
    )

    mocked_project_calls["_update_project_state.notify_project_node_update"] = (
        mocker.patch(
            "simcore_service_webserver.projects._projects_service.notify_project_node_update",
            autospec=True,
        )
    )

    mocked_project_calls["_update_project_state.notify_project_state_update"] = (
        mocker.patch(
            "simcore_service_webserver.projects._projects_service.notify_project_state_update",
            autospec=True,
        )
    )

    return mocked_project_calls


@pytest.fixture
async def with_started_listening_task(client: TestClient) -> AsyncIterator:
    assert client.app
    async for _comp_task in create_comp_tasks_listening_task(client.app):
        # first call creates the task, second call cleans it
        yield


@dataclass(frozen=True, slots=True)
class _CompTaskChangeParams:
    update_values: dict[str, Any]
    expected_calls: list[str]


async def _assert_listener_triggers(
    mock_project_subsystem: dict[str, mock.Mock], expected_calls: list[str]
) -> None:
    for call_name, mocked_call in mock_project_subsystem.items():
        if call_name in expected_calls:
            async for attempt in AsyncRetrying(
                wait=wait_fixed(1),
                stop=stop_after_delay(10),
                retry=retry_if_exception_type(AssertionError),
                before_sleep=before_sleep_log(logger, logging.INFO),
                reraise=True,
            ):
                with attempt:
                    mocked_call.assert_called_once()

        else:
            mocked_call.assert_not_called()


@pytest.mark.parametrize(
    "task_class", [NodeClass.COMPUTATIONAL, NodeClass.INTERACTIVE, NodeClass.FRONTEND]
)
@pytest.mark.parametrize(
    "params",
    [
        pytest.param(
            _CompTaskChangeParams(
                {
                    "outputs": {"some new stuff": "it is new"},
                },
                ["update_node_outputs"],
            ),
            id="new output shall trigger",
        ),
        pytest.param(
            _CompTaskChangeParams(
                {"state": StateType.ABORTED},
                [
                    "_update_project_state.update_project_node_state",
                    "_update_project_state.notify_project_node_update",
                    "_update_project_state.notify_project_state_update",
                ],
            ),
            id="new state shall trigger",
        ),
        pytest.param(
            _CompTaskChangeParams(
                {
                    "outputs": {"some new stuff": "it is new"},
                    "state": StateType.ABORTED,
                },
                [
                    "update_node_outputs",
                    "_update_project_state.update_project_node_state",
                    "_update_project_state.notify_project_node_update",
                    "_update_project_state.notify_project_state_update",
                ],
            ),
            id="new output and state shall double trigger",
        ),
        pytest.param(
            _CompTaskChangeParams({"inputs": {"should not trigger": "right?"}}, []),
            id="no new output or state shall not trigger",
        ),
    ],
)
@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_db_listener_triggers_on_event(
    sqlalchemy_async_engine: AsyncEngine,
    mock_project_subsystem: dict[str, mock.Mock],
    logged_user: UserInfoDict,
    project: Callable[..., Awaitable[ProjectAtDB]],
    pipeline: Callable[..., dict[str, Any]],
    comp_task: Callable[..., dict[str, Any]],
    with_started_listening_task: None,
    params: _CompTaskChangeParams,
    task_class: NodeClass,
    faker: Faker,
):
    some_project = await project(logged_user)
    pipeline(project_id=f"{some_project.uuid}")
    task = comp_task(
        project_id=f"{some_project.uuid}",
        node_id=faker.uuid4(),
        outputs=json.dumps({}),
        node_class=task_class,
    )
    async with sqlalchemy_async_engine.begin() as conn:
        # let's update some values
        await conn.execute(
            comp_tasks.update()
            .values(**params.update_values)
            .where(comp_tasks.c.task_id == task["task_id"])
        )

    await _assert_listener_triggers(mock_project_subsystem, params.expected_calls)
