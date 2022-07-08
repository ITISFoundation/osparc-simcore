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
from typing import AsyncIterator, Callable

import pytest
from asgi_lifespan import LifespanManager
from fastapi import Depends, FastAPI, status
from httpx import AsyncClient
from pydantic import AnyHttpUrl, parse_obj_as
from servicelib.fastapi.long_running import client, server

CURRENT_FILE = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve()
CURRENT_DIR = CURRENT_FILE.parent


# NOTE: `mock_server_app` needs to be defined at module level so uvicorn can import it
# SERVER SETUP

mock_server_app = FastAPI(title="app containing the server")

server.setup(mock_server_app)


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
            print(f"progress {percent}")
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


## FIXTURES - SERVER


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
        print("\nStarted", proc.args)

        # some time to start
        await asyncio.sleep(2)

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


## FIXTURES - CLIENT


@pytest.fixture
async def client_app() -> AsyncIterator[FastAPI]:
    app = FastAPI()
    # TODO: faster polling here!!!
    # should we maybe move the polling to the task_result context manger? maybe makes more sense
    # seems like a better option for that
    client.setup(app)
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

    # TODO: check why progress is providing an tuple ('', 0.0) not ideal
    # TODO: change when getting the result first provide the last progress update maybe
    # return this with the result?
    # TODO: use faster polling, when configuring client

    def progress_handler(message: str, percent: float) -> None:
        progress_updates.append((message, percent))

    async with client.task_result(
        client_app,
        async_client,
        run_server,
        task_id,
        timeout=2,
        progress=progress_handler,
    ) as string_list:
        assert string_list == [f"{x}" for x in range(10)]

        # assert progress_updates == []
