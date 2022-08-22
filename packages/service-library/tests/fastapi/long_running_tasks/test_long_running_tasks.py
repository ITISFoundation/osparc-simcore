"""
Showcases/tests an example of long running tasks.

How these tests works:
- setup a FastAPI server and launch it in the background.
- client directly makes requests to the FastAPI background client.

"""

# pylint: disable=redefined-outer-name

import asyncio
import sys
from pathlib import Path
from typing import AsyncIterator, Final

import pytest
from asgi_lifespan import LifespanManager
from fastapi import APIRouter, Depends, FastAPI, status
from httpx import AsyncClient
from pydantic import AnyHttpUrl, PositiveFloat, parse_obj_as
from servicelib.fastapi import long_running_tasks
from servicelib.long_running_tasks._models import TaskGet

CURRENT_FILE = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve()
CURRENT_DIR = CURRENT_FILE.parent

ITEM_PUBLISH_SLEEP: Final[float] = 0.1


async def _string_list_task(
    task_progress: long_running_tasks.server.TaskProgress, items: int
) -> list[str]:
    generated_strings = []
    for x in range(items):
        string = f"{x}"
        generated_strings.append(string)
        percent = x / items
        await asyncio.sleep(ITEM_PUBLISH_SLEEP)
        task_progress.publish(message="generated item", percent=percent)
    return generated_strings


@pytest.fixture
def server_routes() -> APIRouter:
    routes = APIRouter()

    @routes.post("/string-list-task", status_code=status.HTTP_202_ACCEPTED)
    async def create_string_list_task(
        task_manager: long_running_tasks.server.TasksManager = Depends(
            long_running_tasks.server.get_tasks_manager
        ),
    ) -> long_running_tasks.server.TaskId:
        # NOTE: TaskProgress is injected by start_task
        task_id = long_running_tasks.server.start_task(
            tasks_manager=task_manager, handler=_string_list_task, items=10
        )
        return task_id

    @routes.post("/waiting-task", status_code=status.HTTP_202_ACCEPTED)
    async def create_waiting_task(
        wait_for: float,
        task_manager: long_running_tasks.server.TasksManager = Depends(
            long_running_tasks.server.get_tasks_manager
        ),
    ) -> long_running_tasks.server.TaskId:
        async def _waiting_task(
            task_progress: long_running_tasks.server.TaskProgress,
            wait_for: PositiveFloat,
        ) -> float:
            task_progress.publish(message="started sleeping", percent=0.0)
            await asyncio.sleep(wait_for)
            task_progress.publish(message="finished sleeping", percent=1.0)
            return 42 + wait_for

        task_id = long_running_tasks.server.start_task(
            tasks_manager=task_manager,
            handler=_waiting_task,
            wait_for=wait_for,
        )
        return task_id

    return routes


@pytest.fixture
async def app(server_routes: APIRouter) -> AsyncIterator[FastAPI]:
    app = FastAPI(title="test app")
    app.include_router(server_routes)
    long_running_tasks.server.setup(app)
    long_running_tasks.client.setup(app)
    async with LifespanManager(app):
        yield app


@pytest.fixture
def high_status_poll_interval() -> PositiveFloat:
    # NOTE: polling very fast to capture all the progress updates and to check
    # that duplicate progress messages do not get sent
    return ITEM_PUBLISH_SLEEP / 5


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


async def test_list_tasks(
    client: AsyncClient,
):
    result = await client.post("/string-list-task")
    assert result.status_code == status.HTTP_202_ACCEPTED
    task_id = result.json()

    result = await client.get("/task")
    assert result.status_code == status.HTTP_200_OK
    list_of_tasks = parse_obj_as(list[TaskGet], result.json())


async def test_workflow(
    app: FastAPI,
    client: AsyncClient,
    high_status_poll_interval: PositiveFloat,
) -> None:
    result = await client.post("/string-list-task")
    assert result.status_code == status.HTTP_202_ACCEPTED
    task_id = result.json()

    progress_updates = []

    async def progress_handler(
        message: long_running_tasks.client.ProgressMessage,
        percent: long_running_tasks.client.ProgressPercent,
        _: long_running_tasks.client.TaskId,
    ) -> None:
        progress_updates.append((message, percent))

    lr_client = long_running_tasks.client.Client(
        app=app,
        async_client=client,
        base_url=parse_obj_as(AnyHttpUrl, f"{client.base_url}"),
    )
    async with long_running_tasks.client.periodic_task_result(
        lr_client,
        task_id,
        task_timeout=10,
        progress_callback=progress_handler,
        status_poll_interval=high_status_poll_interval,
    ) as result:
        string_list = result
        assert string_list == [f"{x}" for x in range(10)]

        assert progress_updates == [
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


async def test_error_after_result(
    app: FastAPI,
    client: AsyncClient,
    high_status_poll_interval: PositiveFloat,
) -> None:
    result = await client.post("/string-list-task")
    assert result.status_code == status.HTTP_202_ACCEPTED
    task_id = result.json()

    lr_client = long_running_tasks.client.Client(
        app=app,
        async_client=client,
        base_url=parse_obj_as(AnyHttpUrl, f"{client.base_url}"),
    )
    with pytest.raises(RuntimeError):
        async with long_running_tasks.client.periodic_task_result(
            lr_client,
            task_id,
            task_timeout=10,
            status_poll_interval=high_status_poll_interval,
        ) as result:
            string_list = result
            assert string_list == [f"{x}" for x in range(10)]
            raise RuntimeError("has no influence")
