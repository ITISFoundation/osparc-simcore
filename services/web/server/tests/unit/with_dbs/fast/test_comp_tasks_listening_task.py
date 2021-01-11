# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=no-value-for-parameter

import asyncio
import json
import logging
from asyncio import Future
from typing import Any, Dict, List
from unittest.mock import MagicMock

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


def future_with_result(result: Any) -> asyncio.Future:
    f = Future()
    f.set_result(result)
    return f


@pytest.fixture
async def mock_project_subsystem(mocker) -> Dict:
    mocked_project_calls = {
        "_get_project_owner": mocker.patch(
            "simcore_service_webserver.computation_comp_tasks_listening_task._get_project_owner",
            return_value=future_with_result(""),
        ),
        "_update_project_state": mocker.patch(
            "simcore_service_webserver.computation_comp_tasks_listening_task._update_project_state",
            return_value=future_with_result(""),
        ),
        "_update_project_outputs": mocker.patch(
            "simcore_service_webserver.computation_comp_tasks_listening_task._update_project_outputs",
            return_value=future_with_result(""),
        ),
    }
    yield mocked_project_calls


async def test_mock_project_api(loop, mock_project_subsystem: Dict):
    from simcore_service_webserver.computation_comp_tasks_listening_task import (
        _get_project_owner,
        _update_project_outputs,
        _update_project_state,
    )

    assert isinstance(_get_project_owner, MagicMock)
    assert isinstance(_update_project_state, MagicMock)
    assert isinstance(_update_project_outputs, MagicMock)


@pytest.fixture
async def comp_task_listening_task(
    loop, mock_project_subsystem: Dict, client
) -> asyncio.Task:
    listening_task = loop.create_task(comp_tasks_listening_task(client.app))
    yield listening_task

    listening_task.cancel()
    await listening_task


MAX_TIMEOUT_S = 10
logger = logging.getLogger(__name__)


@tenacity.retry(
    wait=tenacity.wait_fixed(1),
    stop=tenacity.stop_after_delay(MAX_TIMEOUT_S),
    retry=tenacity.retry_if_exception_type(AssertionError),
    before=tenacity.before_log(logger, logging.INFO),
    reraise=True,
)
async def _wait_for_call(mock_fct):
    mock_fct.assert_called()


@pytest.mark.parametrize(
    "task_class", [NodeClass.COMPUTATIONAL, NodeClass.INTERACTIVE, NodeClass.FRONTEND]
)
@pytest.mark.parametrize(
    "upd_value, exp_calls",
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
    upd_value: Dict[str, Any],
    exp_calls: List[str],
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
            .values(**upd_value)
            .where(comp_tasks.c.task_id == task["task_id"])
        )
        for key, mock_fct in mock_project_subsystem.items():
            if key in exp_calls:
                await _wait_for_call(mock_fct)
            else:
                mock_fct.assert_not_called()
