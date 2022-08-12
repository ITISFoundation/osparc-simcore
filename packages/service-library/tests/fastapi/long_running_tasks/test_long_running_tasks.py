"""
Showcases/tests an example of long running tasks.

How these tests works:
- setup a FastAPI server and launch it in the background.
- client directly makes requests to the FastAPI background client.

"""

# pylint: disable=redefined-outer-name

import asyncio
import subprocess
import sys
from pathlib import Path
from typing import AsyncIterator, Callable, Final

import pytest
from asgi_lifespan import LifespanManager
from fastapi import Depends, FastAPI, status
from httpx import AsyncClient
from pydantic import AnyHttpUrl, PositiveFloat, parse_obj_as
from servicelib.fastapi import long_running_tasks
from tenacity._asyncio import AsyncRetrying
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

CURRENT_FILE = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve()
CURRENT_DIR = CURRENT_FILE.parent

ITEM_PUBLISH_SLEEP: Final[float] = 0.1

# UTILS


def create_mock_app() -> FastAPI:
    mock_server_app = FastAPI(title="app containing the server")

    long_running_tasks.server.setup(mock_server_app)

    @mock_server_app.get("/")
    def health() -> None:
        """used to check if application is ready"""

    @mock_server_app.post("/string-list-task", status_code=status.HTTP_202_ACCEPTED)
    async def create_string_list_task(
        task_manager: long_running_tasks.server.TasksManager = Depends(
            long_running_tasks.server.get_tasks_manager
        ),
    ) -> long_running_tasks.server.TaskId:
        async def _string_list_task(
            task_progress: long_running_tasks.server.TaskProgress, items: int
        ) -> list[str]:
            task_progress.publish(message="starting", percent=0)
            generated_strings = []
            for x in range(items):
                string = f"{x}"
                generated_strings.append(string)
                percent = x / items
                await asyncio.sleep(ITEM_PUBLISH_SLEEP)
                task_progress.publish(message="generated item", percent=percent)
            task_progress.publish(message="finished", percent=1)
            return generated_strings

        # NOTE: TaskProgress is injected by start_task
        task_id = long_running_tasks.server.start_task(
            tasks_manager=task_manager, handler=_string_list_task, items=10
        )
        return task_id

    @mock_server_app.post("/waiting-task", status_code=status.HTTP_202_ACCEPTED)
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

    return mock_server_app


async def _wait_server_ready(address: AnyHttpUrl) -> None:
    client = AsyncClient()
    async for attempt in AsyncRetrying(
        wait=wait_fixed(0.1), stop=stop_after_delay(5), reraise=True
    ):
        with attempt:
            print(f"Checking if server running at: {address}")
            response = await client.get(address, timeout=0.1)
            if response.status_code == status.HTTP_202_ACCEPTED:
                return


# FIXTURES - SERVER


@pytest.fixture
async def run_server(get_unused_port: Callable[[], int]) -> AsyncIterator[AnyHttpUrl]:
    port = get_unused_port()
    with subprocess.Popen(
        [
            "uvicorn",
            "--factory",
            f"{CURRENT_FILE.stem}:create_mock_app",
            "--port",
            f"{port}",
        ],
        cwd=f"{CURRENT_DIR}",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ) as proc:

        url = parse_obj_as(AnyHttpUrl, f"http://127.0.0.1:{port}")
        await _wait_server_ready(url)
        print("\nReady and listening on", proc.args)

        # checks started successfully

        def _process_output() -> str:
            assert proc.stdout
            assert proc.stderr
            stdout_decoded = proc.stdout.read().decode("utf-8")
            std_err_decoded = proc.stderr.read().decode("utf-8")
            return f"{stdout_decoded}\n{std_err_decoded}"

        assert not proc.poll(), _process_output()

        yield url

        proc.terminate()
        print(_process_output())


# FIXTURES - CLIENT


@pytest.fixture
def high_status_poll_interval() -> PositiveFloat:
    # NOTE: polling very fast to capture all the progress updates and to check
    # that duplicate progress messages do not get sent
    return ITEM_PUBLISH_SLEEP / 5


@pytest.fixture
async def client_app() -> AsyncIterator[FastAPI]:
    app = FastAPI()

    long_running_tasks.client.setup(app)

    async with LifespanManager(app):
        yield app


@pytest.fixture
async def async_client() -> AsyncClient:
    return AsyncClient()


# TESTS


async def test_workflow(
    run_server: AnyHttpUrl,
    client_app: FastAPI,
    async_client: AsyncClient,
    high_status_poll_interval: PositiveFloat,
) -> None:
    result = await async_client.post(f"{run_server}/string-list-task")
    assert result.status_code == status.HTTP_202_ACCEPTED
    task_id = result.json()

    progress_updates = []

    async def progress_handler(
        message: long_running_tasks.client.ProgressMessage,
        percent: long_running_tasks.client.ProgressPercent,
        _: long_running_tasks.client.TaskId,
    ) -> None:
        progress_updates.append((message, percent))

    client = long_running_tasks.client.Client(
        app=client_app, async_client=async_client, base_url=run_server
    )
    async with long_running_tasks.client.periodic_task_result(
        client,
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
    run_server: AnyHttpUrl,
    client_app: FastAPI,
    async_client: AsyncClient,
    high_status_poll_interval: PositiveFloat,
) -> None:
    result = await async_client.post(f"{run_server}/string-list-task")
    assert result.status_code == status.HTTP_202_ACCEPTED
    task_id = result.json()

    client = long_running_tasks.client.Client(
        app=client_app, async_client=async_client, base_url=run_server
    )
    with pytest.raises(RuntimeError):
        async with long_running_tasks.client.periodic_task_result(
            client,
            task_id,
            task_timeout=10,
            status_poll_interval=high_status_poll_interval,
        ) as result:
            string_list = result
            assert string_list == [f"{x}" for x in range(10)]
            raise RuntimeError("has no influence")
