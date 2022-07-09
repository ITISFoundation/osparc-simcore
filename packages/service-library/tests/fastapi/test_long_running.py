"""
Showcases/tests an example of long running tasks.

How these tests works:
- setup a FastAPI server and lunch it in the background.
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
from httpx import AsyncClient, HTTPError
from pydantic import AnyHttpUrl, parse_obj_as
from servicelib.fastapi.long_running import client, server

CURRENT_FILE = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve()
CURRENT_DIR = CURRENT_FILE.parent

ITEM_PUBLISH_SLEEP: Final[float] = 0.05

# NOTE: `mock_server_app` needs to be defined at module level
# uvicorn is only able to import an object from a module
mock_server_app = FastAPI(title="app containing the server")

server.setup(mock_server_app)


@mock_server_app.get("/")
def health() -> None:
    """used to check if application is ready"""


@mock_server_app.post("/long-running-task")
async def create_task(
    task_manger: server.TaskManager = Depends(server.get_task_manager),
) -> server.TaskId:
    async def _long_running_name_generator(
        task_progress: server.TaskProgress, items: int
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
    task_id = server.start_task(
        task_manager=task_manger,
        handler=_long_running_name_generator,
        items=10,
    )
    return task_id


# UTILS


async def _wait_server_ready(address: AnyHttpUrl) -> None:
    client = AsyncClient()
    while True:
        print(f"Checking if server running at: {address}")
        try:
            response = await client.get(address, timeout=0.1)
            if response.status_code == status.HTTP_200_OK:
                return
        except HTTPError:
            pass
        await asyncio.sleep(0.1)


# FIXTURES - SERVER


@pytest.fixture
async def run_server(get_unused_port: Callable[[], int]) -> AsyncIterator[AnyHttpUrl]:
    port = get_unused_port()
    with subprocess.Popen(
        [
            "uvicorn",
            f"{CURRENT_FILE.stem}:mock_server_app",
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
async def client_app() -> AsyncIterator[FastAPI]:
    app = FastAPI()

    # NOTE: polling very fast to capture all the progress updates and to check
    # that duplicate progress messages do not get sent
    high_status_poll_interval = ITEM_PUBLISH_SLEEP / 4
    client.setup(app, status_poll_interval=high_status_poll_interval)

    async with LifespanManager(app):
        yield app


@pytest.fixture
async def async_client() -> AsyncClient:
    return AsyncClient()


# TESTS


async def test_workflow(
    run_server: AnyHttpUrl, client_app: FastAPI, async_client: AsyncClient
) -> None:
    task_create_url = f"{run_server}/long-running-task"
    result = await async_client.post(task_create_url)
    assert result.status_code == status.HTTP_200_OK
    task_id = result.json()

    progress_updates = []

    def progress_handler(message: str, percent: float) -> None:
        progress_updates.append((message, percent))

    async with client.task_result(
        client_app,
        async_client,
        run_server,
        task_id,
        timeout=10,
        progress=progress_handler,
    ) as string_list:
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
    run_server: AnyHttpUrl, client_app: FastAPI, async_client: AsyncClient
) -> None:
    task_create_url = f"{run_server}/long-running-task"
    result = await async_client.post(task_create_url)
    assert result.status_code == status.HTTP_200_OK
    task_id = result.json()

    with pytest.raises(RuntimeError):
        async with client.task_result(
            client_app, async_client, run_server, task_id, timeout=10
        ) as string_list:
            assert string_list == [f"{x}" for x in range(10)]
            raise RuntimeError("has no influence")
