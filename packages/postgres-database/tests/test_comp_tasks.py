# pylint: disable=no-value-for-parameter
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import asyncio
import json

import pytest
from aiopg.sa.engine import Engine, SAConnection
from aiopg.sa.result import RowProxy
from simcore_postgres_database.models.comp_pipeline import StateType
from simcore_postgres_database.models.comp_tasks import (
    DB_CHANNEL_NAME,
    NodeClass,
    comp_tasks,
)
from sqlalchemy.sql.elements import literal_column


@pytest.fixture()
async def db_connection(pg_engine: Engine) -> SAConnection:
    async with pg_engine.acquire() as conn:
        yield conn


@pytest.fixture()
async def db_notification_queue(db_connection: SAConnection) -> asyncio.Queue:
    listen_query = f"LISTEN {DB_CHANNEL_NAME};"
    await db_connection.execute(listen_query)
    notifications_queue: asyncio.Queue = db_connection.connection.notifies
    assert notifications_queue.empty()
    yield notifications_queue

    assert (
        notifications_queue.empty()
    ), f"the notification queue was not emptied: {notifications_queue.qsize()} remaining notifications"


@pytest.fixture()
async def task(
    db_connection: SAConnection,
    db_notification_queue: asyncio.Queue,
    task_class: NodeClass,
) -> dict:
    result = await db_connection.execute(
        comp_tasks.insert()
        .values(outputs=json.dumps({}), node_class=task_class)
        .returning(literal_column("*"))
    )
    row: RowProxy = await result.fetchone()
    task = dict(row)

    assert (
        db_notification_queue.empty()
    ), "database triggered change although it should only trigger on updates!"

    yield task


async def _assert_notification_queue_status(
    notification_queue: asyncio.Queue, num_exp_messages: int
) -> list[dict]:
    if num_exp_messages > 0:
        assert not notification_queue.empty()

    tasks = []
    for n in range(num_exp_messages):
        msg = await notification_queue.get()

        assert msg, "notification msg from postgres is empty!"
        task_data = json.loads(msg.payload)

        for k in ["table", "changes", "action", "data"]:
            assert k in task_data, f"invalid structure, expected [{k}] in {task_data}"

        tasks.append(task_data)
    assert (
        notification_queue.empty()
    ), f"there are {notification_queue.qsize()} remaining messages in the queue"

    return tasks


async def _update_comp_task_with(conn: SAConnection, task: dict, **kwargs):
    await conn.execute(
        comp_tasks.update()
        .values(**kwargs)
        .where(comp_tasks.c.task_id == task["task_id"])
    )


@pytest.mark.parametrize(
    "task_class",
    [(NodeClass.COMPUTATIONAL), (NodeClass.INTERACTIVE), (NodeClass.FRONTEND)],
)
async def test_listen_query(
    db_notification_queue: asyncio.Queue,
    db_connection: SAConnection,
    task: dict,
):
    """this tests how the postgres LISTEN query and in particular the aiopg implementation of it works"""
    # let's test the trigger
    updated_output = {"some new stuff": "it is new"}
    await _update_comp_task_with(
        db_connection, task, outputs=updated_output, state=StateType.ABORTED
    )
    tasks = await _assert_notification_queue_status(db_notification_queue, 1)
    assert tasks[0]["changes"] == ["modified", "outputs", "state"]
    assert (
        tasks[0]["data"]["outputs"] == updated_output
    ), f"the data received from the database is {tasks[0]}, expected new output is {updated_output}"

    # setting the exact same data twice triggers only ONCE
    updated_output = {"some new stuff": "it is newer"}
    await _update_comp_task_with(db_connection, task, outputs=updated_output)
    await _update_comp_task_with(db_connection, task, outputs=updated_output)
    tasks = await _assert_notification_queue_status(db_notification_queue, 1)
    assert tasks[0]["changes"] == ["modified", "outputs"]
    assert (
        tasks[0]["data"]["outputs"] == updated_output
    ), f"the data received from the database is {tasks[0]}, expected new output is {updated_output}"

    # updating a number of times with different stuff comes out in FIFO order
    NUM_CALLS = 20
    update_outputs = []
    for n in range(NUM_CALLS):
        new_output = {"some new stuff": f"a {n} time"}
        await _update_comp_task_with(db_connection, task, outputs=new_output)
        update_outputs.append(new_output)

    tasks = await _assert_notification_queue_status(db_notification_queue, NUM_CALLS)

    for n, output in enumerate(update_outputs):
        assert tasks[n]["changes"] == ["modified", "outputs"]
        assert (
            tasks[n]["data"]["outputs"] == output
        ), f"the data received from the database is {tasks[n]}, expected new output is {output}"
