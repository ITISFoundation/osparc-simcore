"""
Showcases/tests an example of long running tasks.

How these tests works:
- setup a FastAPI server and launch it in the background.
- client directly makes requests to the FastAPI background client.

"""

# pylint: disable=redefined-outer-name

import asyncio
import json
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Final

import pytest
from asgi_lifespan import LifespanManager
from fastapi import APIRouter, Depends, FastAPI, status
from httpx import AsyncClient
from pydantic import TypeAdapter
from servicelib.fastapi import long_running_tasks
from servicelib.long_running_tasks._models import TaskGet, TaskId
from servicelib.long_running_tasks._task import TaskContext
from tenacity.asyncio import AsyncRetrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed
from yarl import URL

ITEM_PUBLISH_SLEEP: Final[float] = 0.1


async def _string_list_task(
    task_progress: long_running_tasks.server.TaskProgress,
    num_strings: int,
    sleep_time: float,
    fail: bool,
) -> list[str]:
    generated_strings = []
    for index in range(num_strings):
        generated_strings.append(f"{index}")
        await asyncio.sleep(sleep_time)
        task_progress.update(message="generated item", percent=index / num_strings)
        if fail:
            raise RuntimeError("We were asked to fail!!")

    return generated_strings


@pytest.fixture
def server_routes() -> APIRouter:
    routes = APIRouter()

    @routes.post(
        "/string-list-task", response_model=TaskId, status_code=status.HTTP_202_ACCEPTED
    )
    async def create_string_list_task(
        num_strings: int,
        sleep_time: float,
        fail: bool = False,
        task_manager: long_running_tasks.server.TasksManager = Depends(
            long_running_tasks.server.get_tasks_manager
        ),
    ) -> long_running_tasks.server.TaskId:
        task_id = long_running_tasks.server.start_task(
            task_manager,
            _string_list_task,
            num_strings=num_strings,
            sleep_time=sleep_time,
            fail=fail,
        )
        return task_id

    return routes


@pytest.fixture
async def app(server_routes: APIRouter) -> AsyncIterator[FastAPI]:
    # overrides fastapi/conftest.py:app
    app = FastAPI(title="test app")
    app.include_router(server_routes)
    long_running_tasks.server.setup(app)
    long_running_tasks.client.setup(app)
    async with LifespanManager(app):
        yield app


@pytest.fixture
def start_long_running_task() -> Callable[[FastAPI, AsyncClient], Awaitable[TaskId]]:
    async def _caller(app: FastAPI, client: AsyncClient, **query_kwargs) -> TaskId:
        url = URL(app.url_path_for("create_string_list_task")).update_query(
            num_strings=10, sleep_time=f"{0.2}", **query_kwargs
        )
        resp = await client.post(f"{url}")
        assert resp.status_code == status.HTTP_202_ACCEPTED
        task_id = TypeAdapter(long_running_tasks.server.TaskId).validate_python(
            resp.json()
        )
        return task_id

    return _caller


@pytest.fixture
def wait_for_task() -> Callable[
    [FastAPI, AsyncClient, TaskId, TaskContext], Awaitable[None]
]:
    async def _waiter(
        app: FastAPI,
        client: AsyncClient,
        task_id: TaskId,
        task_context: TaskContext,
    ) -> None:
        status_url = URL(
            app.url_path_for("get_task_status", task_id=task_id)
        ).with_query(task_context)
        async for attempt in AsyncRetrying(
            wait=wait_fixed(0.1),
            stop=stop_after_delay(60),
            reraise=True,
            retry=retry_if_exception_type(AssertionError),
        ):
            with attempt:
                result = await client.get(f"{status_url}")
                assert result.status_code == status.HTTP_200_OK
                task_status = long_running_tasks.server.TaskStatus.model_validate(
                    result.json()
                )
                assert task_status
                assert task_status.done

    return _waiter


async def test_workflow(
    app: FastAPI,
    client: AsyncClient,
    start_long_running_task: Callable[[FastAPI, AsyncClient], Awaitable[TaskId]],
) -> None:
    task_id = await start_long_running_task(app, client)

    progress_updates = []
    status_url = app.url_path_for("get_task_status", task_id=task_id)
    async for attempt in AsyncRetrying(
        wait=wait_fixed(0.1),
        stop=stop_after_delay(60),
        reraise=True,
        retry=retry_if_exception_type(AssertionError),
    ):
        with attempt:
            result = await client.get(f"{status_url}")
            assert result.status_code == status.HTTP_200_OK
            task_status = long_running_tasks.server.TaskStatus.model_validate(
                result.json()
            )
            assert task_status
            progress_updates.append(
                (task_status.task_progress.message, task_status.task_progress.percent)
            )
            print(f"<-- received task status: {task_status.model_dump_json(indent=2)}")
            assert task_status.done, "task incomplete"
            print(
                f"-- waiting for task status completed successfully: {json.dumps(attempt.retry_state.retry_object.statistics, indent=2)}"
            )

    EXPECTED_MESSAGES = [
        ("starting", 0.0),
        ("generated item", 0.0),
        ("generated item", 0.1),
        ("generated item", 0.2),
        ("generated item", 0.3),
        ("generated item", 0.4),
        ("generated item", 0.5),
        ("generated item", 0.6),
        ("generated item", 0.7),
        ("generated item", 0.8),
        ("finished", 1.0),
    ]
    assert all(x in progress_updates for x in EXPECTED_MESSAGES)
    # now check the result
    result_url = app.url_path_for("get_task_result", task_id=task_id)
    result = await client.get(f"{result_url}")
    # NOTE: this is DIFFERENT than with aiohttp where we return the real result
    assert result.status_code == status.HTTP_200_OK
    task_result = long_running_tasks.server.TaskResult.model_validate(result.json())
    assert not task_result.error
    assert task_result.result == [f"{x}" for x in range(10)]
    # getting the result again should raise a 404
    result = await client.get(result_url)
    assert result.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.parametrize(
    "method, route_name",
    [
        ("GET", "get_task_status"),
        ("GET", "get_task_result"),
        ("DELETE", "cancel_and_delete_task"),
    ],
)
async def test_get_task_wrong_task_id_raises_not_found(
    app: FastAPI, client: AsyncClient, method: str, route_name: str
):
    url = app.url_path_for(route_name, task_id="fake_task_id")
    result = await client.request(method, f"{url}")
    assert result.status_code == status.HTTP_404_NOT_FOUND


async def test_failing_task_returns_error(
    app: FastAPI,
    client: AsyncClient,
    start_long_running_task: Callable[[FastAPI, AsyncClient], Awaitable[TaskId]],
    wait_for_task: Callable[
        [FastAPI, AsyncClient, TaskId, TaskContext], Awaitable[None]
    ],
) -> None:
    task_id = await start_long_running_task(app, client, fail=f"{True}")
    # wait for it to finish
    await wait_for_task(app, client, task_id, {})
    # get the result
    result_url = app.url_path_for("get_task_result", task_id=task_id)
    result = await client.get(f"{result_url}")
    assert result.status_code == status.HTTP_200_OK
    task_result = long_running_tasks.server.TaskResult.model_validate(result.json())

    assert not task_result.result
    assert task_result.error
    assert task_result.error.startswith(f"Task {task_id} finished with exception: ")
    assert 'raise RuntimeError("We were asked to fail!!")' in task_result.error
    # NOTE: this is not yet happening with fastapi version of long running task
    # assert "errors" in task_result.error
    # assert len(task_result.error["errors"]) == 1
    # assert task_result.error["errors"][0]["code"] == "RuntimeError"
    # assert task_result.error["errors"][0]["message"] == "We were asked to fail!!"


async def test_get_results_before_tasks_finishes_returns_404(
    app: FastAPI,
    client: AsyncClient,
    start_long_running_task: Callable[[FastAPI, AsyncClient], Awaitable[TaskId]],
):
    task_id = await start_long_running_task(app, client)

    result_url = app.url_path_for("get_task_result", task_id=task_id)
    result = await client.get(f"{result_url}")
    assert result.status_code == status.HTTP_404_NOT_FOUND


async def test_cancel_task(
    app: FastAPI,
    client: AsyncClient,
    start_long_running_task: Callable[[FastAPI, AsyncClient], Awaitable[TaskId]],
):
    task_id = await start_long_running_task(app, client)

    # cancel the task
    delete_url = app.url_path_for("cancel_and_delete_task", task_id=task_id)
    result = await client.delete(f"{delete_url}")
    assert result.status_code == status.HTTP_204_NO_CONTENT

    # it should be gone, so no status
    result_url = app.url_path_for("get_task_status", task_id=task_id)
    result = await client.get(f"{result_url}")
    assert result.status_code == status.HTTP_404_NOT_FOUND
    # and also no results
    result_url = app.url_path_for("get_task_result", task_id=task_id)
    result = await client.get(f"{result_url}")
    assert result.status_code == status.HTTP_404_NOT_FOUND

    # try cancelling again
    result = await client.delete(f"{delete_url}")
    assert result.status_code == status.HTTP_404_NOT_FOUND


async def test_list_tasks_empty_list(app: FastAPI, client: AsyncClient):
    # initially empty
    list_url = app.url_path_for("list_tasks")
    result = await client.get(f"{list_url}")
    assert result.status_code == status.HTTP_200_OK
    list_of_tasks = TypeAdapter(list[TaskGet]).validate_python(result.json())
    assert list_of_tasks == []


async def test_list_tasks(
    app: FastAPI,
    client: AsyncClient,
    start_long_running_task: Callable[[FastAPI, AsyncClient], Awaitable[TaskId]],
    wait_for_task: Callable[
        [FastAPI, AsyncClient, TaskId, TaskContext], Awaitable[None]
    ],
):
    # now start a few tasks
    NUM_TASKS = 10
    results = await asyncio.gather(
        *(start_long_running_task(app, client) for _ in range(NUM_TASKS))
    )

    # check we have the full list
    list_url = app.url_path_for("list_tasks")
    result = await client.get(f"{list_url}")
    assert result.status_code == status.HTTP_200_OK
    list_of_tasks = TypeAdapter(list[TaskGet]).validate_python(result.json())
    assert len(list_of_tasks) == NUM_TASKS

    # now wait for them to finish
    await asyncio.gather(
        *(wait_for_task(app, client, task_id, {}) for task_id in results)
    )
    # now get the result one by one

    for task_index, task_id in enumerate(results):
        result_url = app.url_path_for("get_task_result", task_id=task_id)
        await client.get(f"{result_url}")
        # the list shall go down one by one
        result = await client.get(f"{list_url}")
        assert result.status_code == status.HTTP_200_OK
        list_of_tasks = TypeAdapter(list[TaskGet]).validate_python(result.json())
        assert len(list_of_tasks) == NUM_TASKS - (task_index + 1)
