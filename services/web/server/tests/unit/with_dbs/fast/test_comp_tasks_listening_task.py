# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=no-value-for-parameter

import asyncio
import json
from asyncio import Future
from unittest.mock import MagicMock

import aiopg.sa
import pytest
import sqlalchemy as sa
from _pytest.nodes import Node
from aiopg.sa.result import RowProxy
from sqlalchemy.sql.elements import literal_column

from servicelib.application_keys import APP_DB_ENGINE_KEY
from simcore_postgres_database.models.comp_tasks import NodeClass, comp_tasks
from simcore_postgres_database.webserver_models import DB_CHANNEL_NAME
from simcore_service_webserver.computation_comp_tasks_listening_task import listen


def future_with_result(result):
    f = Future()
    f.set_result(result)
    return f


@pytest.fixture
def mock_project_subsystem(mocker):
    mock_project_api = mocker.patch(
        "simcore_service_webserver.projects.projects_api.get_project_for_user",
        return_value=future_with_result(""),
    )
    yield mock_project_api


async def test_mock_project_api(mock_project_subsystem):
    from simcore_service_webserver.projects.projects_api import get_project_for_user

    assert isinstance(get_project_for_user, MagicMock)


async def test_listen_query(client):
    listen_query = f"LISTEN {DB_CHANNEL_NAME};"
    db_engine: aiopg.sa.Engine = client.app[APP_DB_ENGINE_KEY]
    async with db_engine.acquire() as conn:
        await conn.execute(listen_query)
        notifications_queue: asyncio.Queue = conn.connection.notifies
        assert notifications_queue.empty()
        # let's put some stuff in there now
        result = await conn.execute(
            comp_tasks.insert()
            .values(outputs=json.dumps({}), node_class=NodeClass.COMPUTATIONAL)
            .returning(literal_column("*"))
        )
        row: RowProxy = await result.fetchone()
        task = dict(row)
        # the queue should still be empty because we only check on update
        assert notifications_queue.empty()
        # let's update that thing now
        await conn.execute(
            comp_tasks.update()
            .values(outputs={"some new stuff": "it is new"})
            .where(comp_tasks.c.task_id == task["task_id"])
        )
        await asyncio.sleep(5)
        # await conn.execute(listen_query)
        # notifications_queue: asyncio.Queue = conn.connection.notifies
        assert not notifications_queue.empty()
        msg = await notifications_queue.get()
        assert notifications_queue.empty()
        assert msg, "notification msg from postgres is empty!"

        task_data = json.loads(msg.payload)
        assert task_data["data"]["outputs"] == {"some new stuff": "it is new"}
