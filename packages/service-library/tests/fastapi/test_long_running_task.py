# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import asyncio
from datetime import datetime
from typing import AsyncIterable

import pytest
from asgi_lifespan import LifespanManager
from fastapi import APIRouter, Depends, FastAPI, status
from servicelib.fastapi import long_running
from servicelib.fastapi.long_running import (
    ProgressHandler,
    TaskId,
    TaskManager,
    TaskStatus,
    get_task_manager,
    start_task,
)
from servicelib.fastapi.long_running._errors import (
    TaskAlreadyRunningError,
    TaskCancelledError,
    TaskExceptionError,
    TaskNotCompletedError,
    TaskNotFoundError,
)

# UTILS


async def a_background_task(
    progress: ProgressHandler,
    raise_when_finished: bool,
    total_sleep: int,
) -> int:
    """sleeps and raises an error or returns 42"""
    for i in range(total_sleep):
        await asyncio.sleep(1)
        progress.update_progress(percent=float((i + 1) / total_sleep))
    if raise_when_finished:
        raise RuntimeError("raised this error as instructed")

    return 42


async def fast_background_task(progress: ProgressHandler) -> int:
    """this task does nothing and returns a constant"""
    return 42


async def failing_background_task(progress: ProgressHandler) -> None:
    """this task does nothing and returns a constant"""
    raise RuntimeError("failing asap")


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
            handler=a_background_task,
            raise_when_finished=raise_when_finished,
            total_sleep=2,
        )
        return task_id

    return router


@pytest.fixture
async def bg_task_app(user_routes: APIRouter) -> AsyncIterable[FastAPI]:
    app = FastAPI()

    app.include_router(user_routes)

    long_running.setup_server(app)
    async with LifespanManager(app):
        yield app


@pytest.fixture
def task_manager(bg_task_app: FastAPI) -> TaskManager:
    return bg_task_app.state.long_running_task_manager


# TESTS


async def test_unique_task_already_running(task_manager: TaskManager) -> None:
    async def unique_task(progress: ProgressHandler) -> None:
        await asyncio.sleep(1)

    start_task(task_manager=task_manager, handler=unique_task, unique=True)

    # ensure unique running task regardless of how many times it gets started
    for _ in range(5):
        with pytest.raises(TaskAlreadyRunningError) as exec_info:
            start_task(task_manager=task_manager, handler=unique_task, unique=True)
        assert f"{exec_info.value}".startswith(
            f"{unique_task.__qualname__} must be unique, found:"
        )


async def test_start_multiple_not_unique_tasks(task_manager: TaskManager) -> None:
    async def not_unique_task(progress: ProgressHandler) -> None:
        await asyncio.sleep(1)

    for _ in range(5):
        start_task(task_manager=task_manager, handler=not_unique_task)


def test_get_task_id() -> None:
    assert TaskManager.get_task_id("") != TaskManager.get_task_id("")


async def test_get_status(task_manager: TaskManager) -> None:
    task_id = start_task(
        task_manager=task_manager,
        handler=a_background_task,
        raise_when_finished=False,
        total_sleep=10,
    )
    task_status = task_manager.get_status(task_id)
    assert isinstance(task_status, TaskStatus)
    assert task_status.progress.message == ""
    assert task_status.progress.percent == 0.0
    assert task_status.done == False
    assert task_status.successful == False
    assert isinstance(task_status.started, datetime)


async def test_get_status_missing(task_manager: TaskManager) -> None:
    with pytest.raises(TaskNotFoundError) as exec_info:
        task_manager.get_status("missing_task_id")
    assert f"{exec_info.value}" == "No task with missing_task_id found"


async def test_get_result(task_manager: TaskManager) -> None:
    task_id = start_task(task_manager=task_manager, handler=fast_background_task)
    await asyncio.sleep(0.1)
    result = task_manager.get_result(task_id)
    assert result == 42


async def test_get_result_missing(task_manager: TaskManager) -> None:
    with pytest.raises(TaskNotFoundError) as exec_info:
        task_manager.get_result("missing_task_id")
    assert f"{exec_info.value}" == "No task with missing_task_id found"


async def test_get_result_finished_with_error(task_manager: TaskManager) -> None:
    task_id = start_task(task_manager=task_manager, handler=failing_background_task)

    can_continue = True
    while can_continue:
        try:
            task_manager.get_result(task_id)
        except TaskNotCompletedError:
            can_continue = False

        await asyncio.sleep(0.1)

    with pytest.raises(TaskExceptionError) as exec_info:
        task_manager.get_result(task_id)
    assert isinstance(exec_info.value.exception, RuntimeError)
    assert f"{exec_info.value.exception}" == "failing asap"


async def test_get_result_task_was_cancelled_multiple_times(
    task_manager: TaskManager,
) -> None:
    task_id = start_task(
        task_manager=task_manager,
        handler=a_background_task,
        raise_when_finished=False,
        total_sleep=10,
    )
    for _ in range(5):
        await task_manager.cancel_task(task_id)
    with pytest.raises(TaskCancelledError) as exec_info:
        task_manager.get_result(task_id)

    assert f"{exec_info.value}" == f"Task {task_id} was cancelled before completing"


async def test_remove_ok(task_manager: TaskManager) -> None:
    task_id = start_task(
        task_manager=task_manager,
        handler=a_background_task,
        raise_when_finished=False,
        total_sleep=10,
    )
    # pylint: disable=protected-access
    assert task_manager._get_tracked_task(task_id)
    await task_manager.remove(task_id)
    with pytest.raises(TaskNotFoundError):
        assert task_manager._get_tracked_task(task_id)
