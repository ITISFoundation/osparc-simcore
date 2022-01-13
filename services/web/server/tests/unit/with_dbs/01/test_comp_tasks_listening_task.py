# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=no-value-for-parameter

import json
import logging
from typing import Any, AsyncIterator, Dict, List
from unittest import mock

import aiopg.sa
import pytest
from aiohttp.test_utils import TestClient
from aiopg.sa.result import RowProxy
from pytest_mock.plugin import MockerFixture
from servicelib.aiohttp.application_keys import APP_DB_ENGINE_KEY
from simcore_postgres_database.models.comp_pipeline import StateType
from simcore_postgres_database.models.comp_tasks import NodeClass, comp_tasks
from simcore_service_webserver.computation_comp_tasks_listening_task import (
    setup_comp_tasks_listening_task,
)
from sqlalchemy.sql.elements import literal_column
from tenacity._asyncio import AsyncRetrying
from tenacity.before_sleep import before_sleep_log
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

logger = logging.getLogger(__name__)


@pytest.fixture
async def mock_project_subsystem(
    mocker: MockerFixture,
) -> AsyncIterator[Dict[str, mock.MagicMock]]:
    mocked_project_calls = {
        "_get_project_owner": mocker.patch(
            "simcore_service_webserver.computation_comp_tasks_listening_task._get_project_owner",
            return_value="",
        ),
        "_update_project_state": mocker.patch(
            "simcore_service_webserver.computation_comp_tasks_listening_task._update_project_state",
            return_value="",
        ),
        "_update_project_outputs": mocker.patch(
            "simcore_service_webserver.computation_comp_tasks_listening_task._update_project_outputs",
            return_value="",
        ),
    }
    yield mocked_project_calls


@pytest.fixture
async def comp_task_listening_task(
    loop, mock_project_subsystem: Dict, client: TestClient
) -> AsyncIterator:
    async for _comp_task in setup_comp_tasks_listening_task(client.app):
        # first call creates the task, second call cleans it
        yield


@pytest.mark.parametrize(
    "task_class", [NodeClass.COMPUTATIONAL, NodeClass.INTERACTIVE, NodeClass.FRONTEND]
)
@pytest.mark.parametrize(
    "update_values, expected_calls",
    [
        pytest.param(
            {
                "outputs": {"some new stuff": "it is new"},
            },
            ["_get_project_owner", "_update_project_outputs"],
            id="new output shall trigger",
        ),
        pytest.param(
            {"state": StateType.ABORTED},
            ["_get_project_owner", "_update_project_state"],
            id="new state shall trigger",
        ),
        pytest.param(
            {"outputs": {"some new stuff": "it is new"}, "state": StateType.ABORTED},
            ["_get_project_owner", "_update_project_outputs", "_update_project_state"],
            id="new output and state shall double trigger",
        ),
        pytest.param(
            {"inputs": {"should not trigger": "right?"}},
            [],
            id="no new outpuot or state shall not trigger",
        ),
    ],
)
async def test_listen_comp_tasks_task(
    mock_project_subsystem: Dict,
    comp_task_listening_task: None,
    client,
    update_values: Dict[str, Any],
    expected_calls: List[str],
    task_class: NodeClass,
):
    db_engine: aiopg.sa.Engine = client.app[APP_DB_ENGINE_KEY]
    async with db_engine.acquire() as conn:
        # let's put some stuff in there now
        result = await conn.execute(
            comp_tasks.insert()
            .values(outputs=json.dumps({}), node_class=task_class)
            .returning(literal_column("*"))
        )
        row: RowProxy = await result.fetchone()
        task = dict(row)

        # let's update some values
        await conn.execute(
            comp_tasks.update()
            .values(**update_values)
            .where(comp_tasks.c.task_id == task["task_id"])
        )

        # tests whether listener gets hooked calls executed
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
                        mocked_call.assert_awaited()

            else:
                mocked_call.assert_not_called()
