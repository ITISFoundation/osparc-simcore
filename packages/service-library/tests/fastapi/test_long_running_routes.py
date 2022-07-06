# pylint: disable=redefined-outer-name

from fastapi import status, APIRouter, FastAPI, Depends
from httpx import AsyncClient, Response
import pytest
import asyncio
from asgi_lifespan import LifespanManager
from servicelib.fastapi.long_running import (
    get_task_manager,
    TaskManager,
    start_task,
    TaskId,
    ProgressHandler,
    server_setup,
)
from typing import AsyncIterable


# UTILS


def _assert_not_found(response: Response, task_id: TaskId) -> None:
    assert response.status_code == status.HTTP_404_NOT_FOUND, response.text
    assert response.json() == {
        "code": "fastapi.long_running.task_not_found",
        "message": f"No task with {task_id} found",
    }


async def short_task(
    progress: ProgressHandler,
    raise_when_finished: bool,
    total_sleep: float,
) -> int:
    """sleeps and raises an error or returns 42"""
    progress.update_progress(percent=0.0, message="starting")
    await asyncio.sleep(total_sleep)
    progress.update_progress(percent=1.0, message="finished")

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
            total_sleep=1,
        )
        return task_id

    return router


@pytest.fixture
async def bg_task_app(
    user_routes: APIRouter, router_prefix: str
) -> AsyncIterable[FastAPI]:
    app = FastAPI()

    app.include_router(user_routes)

    server_setup(app, router_prefix=router_prefix)

    async with LifespanManager(app):
        yield app


# TESTS


@pytest.mark.parametrize("raise_when_finished", [True, False])
async def test_task_workflow(
    async_client: AsyncClient, raise_when_finished: bool, router_prefix: str
) -> None:
    # Using the API to:
    # [x] create task
    # [x] check status
    # [x] get results, which will: returns the result of the task and remove it

    # create task
    create_resp = await async_client.post(
        "/api/create", params=dict(raise_when_finished=raise_when_finished)
    )
    assert create_resp.status_code == status.HTTP_202_ACCEPTED
    task_id = create_resp.json()

    # fetch status
    can_continue = True
    while can_continue:
        status_resp = await async_client.get(f"{router_prefix}/task/{task_id}")
        assert status_resp.status_code == status.HTTP_200_OK
        task_status = status_resp.json()
        can_continue = not task_status["done"]
        await asyncio.sleep(0.5)

    # fetch result
    result_resp = await async_client.get(f"{router_prefix}/task/{task_id}/result")
    if raise_when_finished:
        assert result_resp.status_code == status.HTTP_400_BAD_REQUEST
        assert result_resp.json() == {
            "code": "fastapi.long_running.task_exception_error",
            "message": f"Task {task_id} finished with exception: 'raised this error as instructed'",
        }
    else:
        assert result_resp.status_code == status.HTTP_200_OK
        assert result_resp.json() == 42

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

    # task has not finished, is ongoing
    result_resp = await async_client.get(f"{router_prefix}/task/{task_id}/result")
    assert result_resp.status_code == status.HTTP_400_BAD_REQUEST
    assert result_resp.json() == {
        "code": "fastapi.long_running.task_not_completed",
        "message": f"Task {task_id} has not finished yet",
    }

    # cancel and remove the task
    delete_resp = await async_client.delete(f"{router_prefix}/task/{task_id}")
    assert delete_resp.status_code == status.HTTP_200_OK
    assert delete_resp.json() is None

    # ensure task does not exist any longer
    status_resp = await async_client.get(f"{router_prefix}/task/{task_id}")
    _assert_not_found(status_resp, task_id)

    # task is no longer present
    result_resp = await async_client.get(f"{router_prefix}/task/{task_id}/result")
    _assert_not_found(result_resp, task_id)


# TODO:
# - test to see what happens if this is cancelled while running
# - test to run interferance from other endpoint 2 of them are launched in parallel (and they do not know of each other)
# - .
