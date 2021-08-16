# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=no-value-for-parameter

import asyncio
import json
import logging
from typing import Any, Dict, List

import aiopg.sa
import pytest
import tenacity
from aiopg.sa.result import RowProxy
from servicelib.application_keys import APP_DB_ENGINE_KEY
from simcore_postgres_database.models.comp_pipeline import StateType
from simcore_postgres_database.models.comp_tasks import NodeClass, comp_tasks
from simcore_service_webserver.computation_comp_tasks_listening_task import (
    comp_tasks_listening_task,
)
from sqlalchemy.sql.elements import literal_column

logger = logging.getLogger(__name__)


@pytest.fixture
async def mock_project_subsystem(mocker) -> Dict:
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


async def test_mock_project_api(loop, mock_project_subsystem: Dict, mocker):
    from simcore_service_webserver.computation_comp_tasks_listening_task import (
        _get_project_owner,
        _update_project_outputs,
        _update_project_state,
    )

    assert isinstance(_get_project_owner, mocker.AsyncMock)
    assert isinstance(_update_project_state, mocker.AsyncMock)
    assert isinstance(_update_project_outputs, mocker.AsyncMock)


@pytest.fixture
async def comp_task_listening_task(
    loop, mock_project_subsystem: Dict, client
) -> asyncio.Task:
    listening_task = loop.create_task(comp_tasks_listening_task(client.app))

    yield listening_task

    listening_task.cancel()
    await listening_task


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
    comp_task_listening_task: asyncio.Task,
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
                async for attempt in _async_retry_if_fails():
                    with attempt:
                        mocked_call.assert_awaited()

            else:
                mocked_call.assert_not_called()


def _async_retry_if_fails():
    # Helper that retries to account for some uncontrolled delays
    return tenacity.AsyncRetrying(
        wait=tenacity.wait_fixed(1),
        stop=tenacity.stop_after_delay(10),
        retry=tenacity.retry_if_exception_type(AssertionError),
        before=tenacity.before_log(logger, logging.INFO),
        reraise=True,
    )
