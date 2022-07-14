# pylint: disable=redefined-outer-name
# pylint: disable=protected-access

import asyncio
from typing import AsyncIterable, Final
from black import err

import pytest
from asgi_lifespan import LifespanManager
from fastapi import APIRouter, Depends, FastAPI, status
from httpx import AsyncClient, Response
from pydantic import PositiveFloat, PositiveInt
from servicelib.fastapi.long_running._models import TaskResult
from servicelib.fastapi.long_running.server import (
    TaskId,
    TaskManager,
    TaskProgress,
    get_task_manager,
)
from servicelib.fastapi.long_running.server import setup as setup_server
from servicelib.fastapi.long_running.server import start_task

TASK_SLEEP_INTERVAL: Final[PositiveFloat] = 0.1

# UTILS


def _assert_not_found(response: Response, task_id: TaskId) -> None:
    assert response.status_code == status.HTTP_404_NOT_FOUND, response.text
    assert response.json() == {
        "code": "fastapi.long_running.task_not_found",
        "message": f"No task with {task_id} found",
    }


def assert_expected_tasks(async_client: AsyncClient, task_count: PositiveInt) -> None:
    app: FastAPI = async_client._transport.app
    assert app
    task_manager: TaskManager = app.state.long_running_task_manager
    assert task_manager

    assert len(task_manager.tasks["test_long_running_routes.short_task"]) == task_count


async def short_task(
    task_progress: TaskProgress,
    raise_when_finished: bool,
    total_sleep: float,
) -> int:
    """sleeps and raises an error or returns 42"""
    task_progress.publish(percent=0.0, message="starting")
    await asyncio.sleep(total_sleep)
    task_progress.publish(percent=1.0, message="finished")

    if raise_when_finished:
        raise RuntimeError("raised this error as instructed")

    return 42


# FIXTURES


@pytest.fixture
def user_routes() -> APIRouter:
    router = APIRouter()

    @router.post("/api/create", status_code=status.HTTP_202_ACCEPTED)
    async def create_task_user_defined_route(
        raise_when_finished: bool, task_manger: TaskManager = Depends(get_task_manager)
    ) -> TaskId:
        task_id = start_task(
            task_manager=task_manger,
            handler=short_task,
            raise_when_finished=raise_when_finished,
            total_sleep=TASK_SLEEP_INTERVAL,
        )
        return task_id

    return router


@pytest.fixture
async def bg_task_app(
    user_routes: APIRouter, router_prefix: str
) -> AsyncIterable[FastAPI]:
    app = FastAPI()

    app.include_router(user_routes)

    setup_server(app, router_prefix=router_prefix)

    async with LifespanManager(app):
        yield app


# TESTS


@pytest.mark.parametrize("finish_with_error", [True, False])
async def test_task_workflow(
    async_client: AsyncClient, finish_with_error: bool, router_prefix: str
) -> None:
    # Using the API to:
    # [x] create task
    # [x] check status
    # [x] get results, which will: returns the result of the task and remove it

    # create task
    create_resp = await async_client.post(
        "/api/create", params=dict(raise_when_finished=finish_with_error)
    )
    assert create_resp.status_code == status.HTTP_202_ACCEPTED
    task_id = create_resp.json()
    assert_expected_tasks(async_client, 1)

    # fetch status
    can_continue = True
    while can_continue:
        status_resp = await async_client.get(f"{router_prefix}/task/{task_id}")
        assert status_resp.status_code == status.HTTP_200_OK
        task_status = status_resp.json()
        can_continue = not task_status["done"]
        await asyncio.sleep(TASK_SLEEP_INTERVAL / 3)

    # fetch result
    result_resp = await async_client.get(f"{router_prefix}/task/{task_id}/result")
    assert_expected_tasks(async_client, 0)
    assert result_resp.status_code == status.HTTP_200_OK
    if finish_with_error:
        task_result = TaskResult.parse_obj(result_resp.json())
        assert task_result.result is None
        assert task_result.error is not None
        assert task_result.error.startswith(f"Task {task_id} finished with exception: ")
        assert (
            'raise RuntimeError("raised this error as instructed")' in task_result.error
        )
    else:
        assert result_resp.json() == TaskResult(result=42, error=None)

    # ensure task does not exist any longer
    status_when_finished_resp = await async_client.get(
        f"{router_prefix}/task/{task_id}"
    )
    _assert_not_found(status_when_finished_resp, task_id)


async def test_delete_workflow(async_client: AsyncClient, router_prefix: str) -> None:

    # create task
    create_resp = await async_client.post(
        "/api/create", params=dict(raise_when_finished=False)
    )
    assert create_resp.status_code == status.HTTP_202_ACCEPTED
    task_id = create_resp.json()
    assert_expected_tasks(async_client, 1)

    # task has not finished, is ongoing
    result_resp = await async_client.get(f"{router_prefix}/task/{task_id}/result")
    assert result_resp.status_code == status.HTTP_400_BAD_REQUEST
    assert result_resp.json() == {
        "code": "fastapi.long_running.task_not_completed",
        "message": f"Task {task_id} has not finished yet",
    }
    assert_expected_tasks(async_client, 1)

    # cancel and remove the task
    delete_resp = await async_client.delete(f"{router_prefix}/task/{task_id}")
    assert delete_resp.status_code == status.HTTP_200_OK
    assert delete_resp.json() is True
    assert_expected_tasks(async_client, 0)

    # ensure task does not exist any longer
    status_resp = await async_client.get(f"{router_prefix}/task/{task_id}")
    _assert_not_found(status_resp, task_id)

    # task is no longer present
    result_resp = await async_client.get(f"{router_prefix}/task/{task_id}/result")
    _assert_not_found(result_resp, task_id)
