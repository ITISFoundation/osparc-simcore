# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import asyncio
from asyncio import AbstractEventLoop, Task
from datetime import datetime
from typing import AsyncIterable, Callable

import pytest
from async_asgi_testclient import TestClient
from fastapi import APIRouter, FastAPI, Request, Response, status
from fastapi.testclient import TestClient as SyncTestClient
from pydantic import NonNegativeInt
from servicelib.fastapi.requests_decorators import TASK_NAME_PREFIX, cancellable_request


@pytest.fixture
def app() -> FastAPI:

    api_router = APIRouter()

    @api_router.get("/")
    def _get_root():
        return {"name": __name__, "timestamp": datetime.utcnow().isoformat()}

    @api_router.get("/sleep/{delay}")
    @cancellable_request
    async def _cancellable_with_await(_request: Request, delay: NonNegativeInt):
        await asyncio.sleep(delay)

    # @api_router.get("/sleep/{delay}/aio-tasks")
    # @cancellable_request
    # async def _cancellable_with_aio_tasks(_request: Request, delay: NonNegativeInt):
    #    await asyncio.sleep(delay)

    # TODO: handler spawns subprocesses
    # TODO: handler spawns threads
    # TODO: handler spawns aio-tasks
    # TODO: handler with backgroundtask

    _app = FastAPI()
    _app.include_router(api_router)

    return _app


@pytest.fixture
async def test_client(app: FastAPI) -> AsyncIterable[TestClient]:
    async with TestClient(app) as client:
        yield client


@pytest.fixture()
def inspect_app_tasks(
    event_loop: AbstractEventLoop,
) -> Callable[[], list[Task]]:
    """Function to return cancellable tasks"""

    def go():
        return [
            task
            for task in asyncio.all_tasks(event_loop)
            if task.get_name().startswith(f"{TASK_NAME_PREFIX}/")
        ]

    return go


def test_raises_if_wrong_signature_upon_import(app: FastAPI):
    # let's define some routes
    @app.get("/correct")
    @cancellable_request
    async def _correct_signature(_request: Request, x: int):
        ...

    with pytest.raises(ValueError) as exc_info:

        @app.get("/wrong")
        @cancellable_request
        async def _wrong_signature():
            ...

    assert "_wrong_signature" in str(exc_info.value)


async def test_with_non_cancellable_entrypoint(
    test_client: TestClient, inspect_app_tasks: Callable[[], list[Task]]
):
    assert not inspect_app_tasks()

    # NOT cancellable entrypoint
    r = await test_client.get("/")
    assert r.status_code == status.HTTP_200_OK

    assert not inspect_app_tasks()


async def test_cancellable_handler_with_successful_request(
    test_client: TestClient, inspect_app_tasks: Callable[[], list[Task]]
):
    # cancellable entrypoint

    r = await test_client.get("/sleep/0")
    assert r.status_code == status.HTTP_200_OK

    assert all(
        t.done() for t in inspect_app_tasks()
    ), "All tasks (if any) should be done"


@pytest.mark.skip(reason="DEV")
async def test_it(app: FastAPI, inspect_app_tasks: Callable[[], list[Task]]):

    # interrupt request
    with SyncTestClient(app) as test_client:
        with pytest.raises(asyncio.TimeoutError):
            r = test_client.get(
                "/sleep/100", headers={"Connection": "close"}, timeout=0.001
            )

    app_tasks = inspect_app_tasks()
    assert app_tasks
    assert all(not t.done() for t in app_tasks)

    while not all(t.done() for t in app_tasks):
        await asyncio.sleep(0.5)


@pytest.mark.skip(reason="DEV")
async def test_it2(
    test_client: TestClient, inspect_app_tasks: Callable[[], list[Task]]
):
    client_task = asyncio.create_task(test_client.get("/sleep/100"))

    await asyncio.sleep(0.1)

    app_tasks = inspect_app_tasks()
    assert app_tasks
    assert all(not t.done() for t in app_tasks)

    assert client_task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await client_task

    while not all(t.done() for t in app_tasks):
        await asyncio.sleep(0.5)


@pytest.mark.skip(reason="DEV")
async def test_it3(
    test_client: TestClient, inspect_app_tasks: Callable[[], list[Task]]
):

    # Client cancels
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(test_client.get("/sleep/100"), timeout=0.5)

    cancellable_tasks = inspect_app_tasks()
    # assert cancellable_tasks

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(test_client.get("/sleep-uncancelled/100"), timeout=0.5)
    cancellable_tasks = inspect_app_tasks()
    # assert cancellable_tasks

    # TODO: check that _create_slow_call was cancelled!
    # probably client

    # are tasks cancelled?
    # create process and cancel
    # create a thread and cancel
    # create a aio task and cancel


@pytest.mark.skip(reason="DEV")
async def test_it4(test_client: TestClient):

    # will cancel
    reqs = [test_client.get("/sleep/5", timeout=1) for _ in range(100)]

    # will
    reqs += [test_client.get("/sleep/1") for _ in range(100)]

    results = await asyncio.gather(*reqs, return_exceptions=True)

    assert all(isinstance(r, Exception) for r in results[:100])
    assert all(
        isinstance(r, Response) and r.status_code == status.HTTP_200_OK
        for r in results[100:]
    )
