"""
Showcases/tests an example of long running tasks.

How these tests works:
- setup a FastAPI server and launch it in the background.
- client directly makes requests to the FastAPI background client.

"""

# pylint: disable=redefined-outer-name

import asyncio
import json
import sys
from pathlib import Path
from typing import Callable, Final

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from pydantic import parse_obj_as

# TESTS
from pytest_simcore.helpers.utils_assert import assert_status
from servicelib.aiohttp import long_running_tasks
from servicelib.json_serialization import json_dumps
from tenacity._asyncio import AsyncRetrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

CURRENT_FILE = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve()
CURRENT_DIR = CURRENT_FILE.parent

ITEM_PUBLISH_SLEEP: Final[float] = 0.2

TASKS_ROUTER_PREFIX: Final[str] = "/futures"


@pytest.fixture
def app() -> web.Application:
    app = web.Application()
    routes = web.RouteTableDef()

    @routes.post("/long_running_task:start")
    async def generate_list_strings(request: web.Request):
        task_manager = long_running_tasks.server.get_task_manager(request.app)
        assert task_manager, "task manager is not initiated!"

        async def _string_list_task(
            task_progress: long_running_tasks.server.TaskProgress, num_strings: int
        ) -> list[str]:
            task_progress.publish(message="starting", percent=0)
            generated_strings = []
            for index in range(num_strings):
                generated_strings.append(f"{index}")
                await asyncio.sleep(ITEM_PUBLISH_SLEEP)
                task_progress.publish(
                    message="generated item", percent=index / num_strings
                )
            task_progress.publish(message="finished", percent=1)
            return generated_strings

        task_id = long_running_tasks.server.start_task(
            task_manager, _string_list_task, num_strings=10
        )
        return web.json_response(
            data={"data": task_id},
            status=web.HTTPAccepted.status_code,
            dumps=json_dumps,
        )

    app.add_routes(routes)
    long_running_tasks.server.setup(app, router_prefix=TASKS_ROUTER_PREFIX)

    return app


@pytest.fixture
def client(
    event_loop: asyncio.AbstractEventLoop,
    aiohttp_client: Callable,
    unused_tcp_port_factory: Callable,
    app: web.Application,
) -> TestClient:

    return event_loop.run_until_complete(
        aiohttp_client(app, server_kwargs={"port": unused_tcp_port_factory()})
    )


async def test_workflow(client: TestClient) -> None:
    result = await client.post(f"/long_running_task:start")
    data, error = await assert_status(result, web.HTTPAccepted)
    assert data
    assert not error
    task_id = parse_obj_as(long_running_tasks.server.TaskId, data)

    # get progress updates
    async for attempt in AsyncRetrying(
        wait=wait_fixed(0.1),
        stop=stop_after_delay(60),
        reraise=True,
        retry=retry_if_exception_type(AssertionError),
    ):
        with attempt:
            result = await client.get(f"{TASKS_ROUTER_PREFIX}/{task_id}")
            data, error = await assert_status(result, web.HTTPOk)
            assert data
            assert not error
            task_status = long_running_tasks.server.TaskStatus.parse_obj(data)
            assert task_status
            print(f"<-- received task status: {task_status.json(indent=2)}")
            assert task_status.done, "task incomplete"
            print(
                f"-- waiting for task status completed successfully: {json.dumps(attempt.retry_state.retry_object.statistics, indent=2)}"
            )

    # now get the result
    result = await client.get(f"{TASKS_ROUTER_PREFIX}/{task_id}/result")
    data, error = await assert_status(result, web.HTTPOk)
    assert data
    assert not error
    task_result = long_running_tasks.server.TaskResult.parse_obj(data)
    assert task_result
    assert task_result.result == [f"{x}" for x in range(10)]
    assert not task_result.error
