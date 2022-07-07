# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import asyncio
from typing import AsyncIterable

import pytest
from asgi_lifespan import LifespanManager
from fastapi import APIRouter, Depends, FastAPI, status
from httpx import AsyncClient
from pydantic import AnyHttpUrl, parse_obj_as
from servicelib.fastapi.long_running._context_manager import _ProgressUpdater
from servicelib.fastapi.long_running._errors import (
    TaskClientResultErrorError,
    TaskClientTimeoutError,
)
from servicelib.fastapi.long_running.client import setup as setup_client
from servicelib.fastapi.long_running.client import task_result
from servicelib.fastapi.long_running.server import (
    ProgressHandler,
    TaskId,
    TaskManager,
    get_task_manager,
)
from servicelib.fastapi.long_running.server import setup as setup_server
from servicelib.fastapi.long_running.server import start_task

# UTILS


async def _assert_task_removed(
    async_client: AsyncClient, task_id: TaskId, router_prefix: str
) -> None:
    result = await async_client.get(f"{router_prefix}/tasks/{task_id}")
    assert result.status_code == status.HTTP_404_NOT_FOUND


# FIXTURES


async def a_test_task(progress: ProgressHandler) -> int:
    progress.update_progress(message="starting", percent=0.0)
    await asyncio.sleep(1)
    progress.update_progress(message="finished", percent=1.0)
    return 42


async def a_failing_test_task(progress: ProgressHandler) -> None:
    progress.update_progress(message="starting", percent=0.0)
    await asyncio.sleep(1)
    progress.update_progress(message="finished", percent=1.0)
    raise RuntimeError("I am failing as requested")


@pytest.fixture
def user_routes() -> APIRouter:
    router = APIRouter()

    @router.get("/api/success", status_code=status.HTTP_200_OK)
    async def create_task_user_defined_route(
        task_manger: TaskManager = Depends(get_task_manager),
    ) -> TaskId:
        task_id = start_task(task_manager=task_manger, handler=a_test_task)
        return task_id

    @router.get("/api/failing", status_code=status.HTTP_200_OK)
    async def create_task_which_fails(
        task_manger: TaskManager = Depends(get_task_manager),
    ) -> TaskId:
        task_id = start_task(task_manager=task_manger, handler=a_failing_test_task)
        return task_id

    return router


@pytest.fixture
async def bg_task_app(
    user_routes: APIRouter, router_prefix: str
) -> AsyncIterable[FastAPI]:
    app = FastAPI()

    app.include_router(user_routes)

    setup_server(app, router_prefix=router_prefix)
    setup_client(app, router_prefix=router_prefix, status_poll_interval=0.2)

    async with LifespanManager(app):
        yield app


# TESTS


async def test_task_result(
    bg_task_app: FastAPI, async_client: AsyncClient, router_prefix: str
) -> None:
    result = await async_client.get("/api/success")
    assert result.status_code == status.HTTP_200_OK, result.text
    task_id = result.json()

    url = parse_obj_as(AnyHttpUrl, "http://backgroud.testserver.io")
    async with task_result(
        bg_task_app, async_client, url, task_id, timeout=10
    ) as result:
        assert result == 42

    await _assert_task_removed(async_client, task_id, router_prefix)


async def test_task_result_times_out(
    bg_task_app: FastAPI, async_client: AsyncClient, router_prefix: str
) -> None:
    result = await async_client.get("/api/success")
    assert result.status_code == status.HTTP_200_OK, result.text
    task_id = result.json()

    url = parse_obj_as(AnyHttpUrl, "http://backgroud.testserver.io")
    timeout = 1
    with pytest.raises(TaskClientTimeoutError) as exec_info:
        async with task_result(
            bg_task_app, async_client, url, task_id, timeout=timeout
        ):
            pass
    assert (
        f"{exec_info.value}"
        == f"Timed out after {timeout} seconds while awaiting '{task_id}' to complete"
    )

    await _assert_task_removed(async_client, task_id, router_prefix)


async def test_task_result_task_result_is_an_error(
    bg_task_app: FastAPI, async_client: AsyncClient, router_prefix: str
) -> None:
    result = await async_client.get("/api/failing")
    assert result.status_code == status.HTTP_200_OK, result.text
    task_id = result.json()

    url = parse_obj_as(AnyHttpUrl, "http://backgroud.testserver.io")
    with pytest.raises(TaskClientResultErrorError) as exec_info:
        async with task_result(bg_task_app, async_client, url, task_id, timeout=10):
            pass
    assert f"{exec_info.value}" == (
        f"Task '{task_id}' did no finish successfully but raised: "
        "{'code': 'fastapi.long_running.task_exception_error', "
        f"'message': \"Task {task_id} finished with exception: "
        "'I am failing as requested'\"}"
    )

    await _assert_task_removed(async_client, task_id, router_prefix)


@pytest.mark.parametrize("repeat", [1, 2, 10])
def test_progress_updater(repeat: int) -> None:
    counter = 0

    def progress_update(message, percent) -> None:
        nonlocal counter
        counter += 1

    progress_updater = _ProgressUpdater(progress_update)

    # different from None and the last value only
    # triggers once
    for _ in range(repeat):
        progress_updater.update(message="")
        assert counter == 1

    for _ in range(repeat):
        progress_updater.update(percent=0.0)
        assert counter == 2

    for _ in range(repeat):
        progress_updater.update(percent=1.0, message="done")
        assert counter == 3

    # setting percent or message to None
    # will not trigger an event

    for _ in range(repeat):
        progress_updater.update(message=None)
        assert counter == 3

    for _ in range(repeat):
        progress_updater.update(percent=None)
        assert counter == 3

    for _ in range(repeat):
        progress_updater.update(percent=None, message=None)
        assert counter == 3

    for _ in range(repeat):
        progress_updater.update()
        assert counter == 3
