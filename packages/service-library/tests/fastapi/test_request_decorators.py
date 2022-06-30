# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import asyncio
from asyncio import AbstractEventLoop, Task
from datetime import datetime
from typing import AsyncIterable, Callable

import pytest
from async_asgi_testclient import TestClient
from async_asgi_testclient.utils import create_monitored_task, flatten_headers
from fastapi import APIRouter, FastAPI, Request, status
from fastapi.testclient import TestClient as SyncTestClient
from pydantic import NonNegativeInt
from servicelib.fastapi.requests_decorators import TASK_NAME_PREFIX, cancellable_request
from tenacity._asyncio import AsyncRetrying
from tenacity.stop import stop_after_attempt
from tenacity.wait import wait_fixed


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

    # TODO: handler spawns subprocesses
    # TODO: handler spawns threads
    # TODO: handler spawns aio-tasks
    # TODO: handler with backgroundtask

    _app = FastAPI()
    _app.include_router(api_router)

    @_app.on_event("startup")
    async def on_startup():
        _app.state.started = True
        _app.state.stopped = False

    @_app.on_event("shutdown")
    async def on_shutdown():
        _app.state.started = True
        _app.state.stopped = True

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


# TESTS


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


#
# NOTE:
# - Cannot find a way to disconnect a client using the TestClient fixture  :-(
# - Any ideas welcome!
#


@pytest.mark.skip(reason="DEV: cannot emulate disconnect")
async def test_it0(
    app: FastAPI,
    event_loop: asyncio.AbstractEventLoop,
    inspect_app_tasks: Callable[[], list[Task]],
):
    #
    # Extension of TestClient to send a disconnect request
    #
    # It does send a disconnect request but the monitor task
    # interprets it as "separate" and does not cancel the
    # initial
    #
    class TestClientExt(TestClient):
        def disconnect(
            self,
            path: str,
            *,
            method: str = "GET",
            scheme: str = "http",
        ):
            input_queue: asyncio.Queue[dict] = asyncio.Queue()
            output_queue: asyncio.Queue[dict] = asyncio.Queue()
            scope = {
                "type": "http",
                "http_version": "1.1",
                "asgi": {"version": "3.0"},
                "method": method,
                "scheme": scheme,
                "path": path,
                "query_string": b"",
                "root_path": "",
                "headers": flatten_headers({"Connection": "close"}),
            }
            running_task = create_monitored_task(
                self.application(scope, input_queue.get, output_queue.put),
                output_queue.put_nowait,
            )

            send = input_queue.put_nowait
            send({"type": "http.disconnect"})

    # tests ---

    # on_start event not called
    with pytest.raises(AttributeError) as exc_info:
        assert app.state.started
    assert "started" in f"{exc_info.value}"

    # Emulating disconnect
    async with TestClientExt(app) as client:
        assert app.state.started
        assert not app.state.stopped

        client_task = event_loop.create_task(
            client.get("/sleep/100", headers={"Connection": "close"})
        )
        await asyncio.sleep(0.1)  # triggers reg_task to start
        app_tasks = inspect_app_tasks()

        client.disconnect("/sleep/100")  # creates A NEW req that is canceled
        await asyncio.sleep(0.1)

        r = await client_task  # DOES NOT GET CANCELED
        assert all(t.done() for t in app_tasks)

    assert app.state.stopped


@pytest.mark.skip(reason="DEV: cannot emulate disconnect")
async def test_it1(app: FastAPI, inspect_app_tasks: Callable[[], list[Task]]):
    # Emulating disconnect by producing a timemout with syncronous
    # test client

    async with TestClient(app, timeout=0.001) as client:
        with pytest.raises(asyncio.TimeoutError):
            r = await client.get("/sleep/100")

        await asyncio.sleep(1)
        app_tasks = inspect_app_tasks()
        assert app_tasks

        async for attempt in AsyncRetrying(
            wait=wait_fixed(0.5), stop=stop_after_attempt(4)
        ):
            with attempt:
                assert all(t.done() for t in app_tasks)


@pytest.mark.skip(reason="DEV: cannot emulate disconnect")
async def test_it1a(app: FastAPI, inspect_app_tasks: Callable[[], list[Task]]):
    with SyncTestClient(app) as client:
        with pytest.raises(asyncio.TimeoutError):
            r = client.get("/sleep/100", timeout=0.001)

            await asyncio.sleep(1)
            app_tasks = inspect_app_tasks()
            assert app_tasks

            async for attempt in AsyncRetrying(
                wait=wait_fixed(0.5), stop=stop_after_attempt(4)
            ):
                with attempt:
                    assert all(t.done() for t in app_tasks)


@pytest.mark.skip(reason="DEV: cannot emulate disconnect")
async def test_it2(
    test_client: TestClient,
    inspect_app_tasks: Callable[[], list[Task]],
    event_loop: asyncio.AbstractEventLoop,
):
    client_task = event_loop.create_task(test_client.get("/sleep/100"))

    await asyncio.sleep(0.1)  # triggers client_task to start

    app_tasks = inspect_app_tasks()
    assert app_tasks
    assert all(not t.done() for t in app_tasks)

    assert client_task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await client_task

    async for attempt in AsyncRetrying(
        wait=wait_fixed(0.5), stop=stop_after_attempt(4)
    ):
        with attempt:
            assert all(t.done() for t in app_tasks)

    # are tasks cancelled?
    # create process and cancel
    # create a thread and cancel
    # create a aio task and cancel
