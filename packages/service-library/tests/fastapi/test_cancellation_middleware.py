# pylint: disable=redefined-outer-name

import asyncio
import logging
import threading
from collections.abc import Iterator
from threading import Thread
from unittest.mock import AsyncMock

import httpx
import pytest
import uvicorn
import uvloop
from fastapi import APIRouter, BackgroundTasks, FastAPI
from pytest_simcore.helpers.logging_tools import log_context
from servicelib.fastapi.cancellation_middleware import RequestCancellationMiddleware
from servicelib.utils import unused_port
from starlette.types import Message, Receive, Scope, Send
from tenacity import retry, stop_after_delay, wait_fixed
from yarl import URL


@pytest.fixture
def server_done_event() -> threading.Event:
    # This allows communicate an event between the thread where the server is running
    # and the test thread. It is used to signal that the server has completed its task
    # WARNING: do not user asyncio.Event here as it is not thread-safe!
    return threading.Event()


@pytest.fixture
def server_cancelled_mock() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def fastapi_router(server_done_event: threading.Event, server_cancelled_mock: AsyncMock) -> APIRouter:
    router = APIRouter()

    @router.get("/")
    async def root() -> dict[str, str]:
        with log_context(logging.INFO, msg="root endpoint") as ctx:
            ctx.logger.info("root endpoint called")
            return {"message": "Hello, World!"}

    @router.get("/sleep")
    async def sleep(sleep_time: float) -> dict[str, str]:
        with log_context(logging.INFO, msg="sleeper") as ctx:
            try:
                await asyncio.sleep(sleep_time)
                return {"message": f"Slept for {sleep_time} seconds"}
            except asyncio.CancelledError:
                ctx.logger.info("sleeper cancelled!")
                await server_cancelled_mock()
                return {"message": "Cancelled"}
            finally:
                server_done_event.set()

    async def _sleep_in_the_back(sleep_time: float) -> None:
        with log_context(logging.INFO, msg="sleeper in the back") as ctx:
            try:
                await asyncio.sleep(sleep_time)
            except asyncio.CancelledError:
                ctx.logger.info("sleeper in the back cancelled!")
                await server_cancelled_mock()
            finally:
                server_done_event.set()

    @router.get("/sleep-with-background-task")
    async def sleep_with_background_task(sleep_time: float, background_tasks: BackgroundTasks) -> dict[str, str]:
        with log_context(logging.INFO, msg="sleeper with background task"):
            background_tasks.add_task(_sleep_in_the_back, sleep_time)
            return {"message": "Sleeping in the back"}

    return router


@pytest.fixture
def fastapi_app(fastapi_router: APIRouter) -> FastAPI:
    app = FastAPI()
    app.include_router(fastapi_router)

    app.add_middleware(RequestCancellationMiddleware)  # Middleware under test
    return app


@pytest.fixture
def uvicorn_server(fastapi_app: FastAPI) -> Iterator[URL]:
    server_host = "127.0.0.1"
    server_port = unused_port()
    server_url = f"http://{server_host}:{server_port}"

    with log_context(
        logging.INFO,
        msg=f"with uvicorn server on {server_url}",
    ) as ctx:
        config = uvicorn.Config(
            fastapi_app,
            host=server_host,
            port=server_port,
            log_level="error",
            loop="uvloop",
        )
        server = uvicorn.Server(config)

        thread = Thread(target=server.run)
        thread.daemon = True
        thread.start()

        @retry(wait=wait_fixed(0.1), stop=stop_after_delay(10), reraise=True)
        def wait_for_server_ready() -> None:
            response = httpx.get(f"{server_url}/")
            assert response.is_success, f"Server did not start successfully: {response.status_code} {response.text}"

        wait_for_server_ready()

        ctx.logger.info("server ready at: %s", server_url)

        yield URL(server_url)

        server.should_exit = True
        thread.join(timeout=10)


async def test_server_cancels_when_client_disconnects(
    uvicorn_server: URL,
    server_done_event: threading.Event,
    server_cancelled_mock: AsyncMock,
):
    # Implementation of RequestCancellationMiddleware is under test here
    assert isinstance(asyncio.get_running_loop(), uvloop.Loop)

    async with httpx.AsyncClient(base_url=f"{uvicorn_server}") as client:
        # 1. check standard call still complete as expected
        with log_context(logging.INFO, msg="client calling endpoint"):
            response = await client.get("/sleep", params={"sleep_time": 0.1})

        assert response.status_code == 200
        assert response.json() == {"message": "Slept for 0.1 seconds"}

        server_done_event.wait(10)
        server_done_event.clear()

        # 2. check slow call get cancelled
        with log_context(logging.INFO, msg="client calling endpoint for cancellation") as ctx:
            with pytest.raises(httpx.ReadTimeout):
                await client.get(
                    "/sleep",
                    params={"sleep_time": 10},
                    timeout=0.1,  # <--- this will enforce the client to disconnect from the server !
                )
            ctx.logger.info("client disconnected from server")

        # request should have been cancelled after the ReadTimeout!
        server_done_event.wait(5)
        server_cancelled_mock.assert_called_once()
        server_cancelled_mock.reset_mock()
        server_done_event.clear()

        # 3. check background tasks get cancelled as well sadly
        # NOTE: shows that FastAPI BackgroundTasks get cancelled too!
        with log_context(logging.INFO, msg="client calling endpoint for cancellation"):
            response = await client.get(
                "/sleep-with-background-task",
                params={"sleep_time": 2},
            )
            assert response.status_code == 200

        # request should have been cancelled after the ReadTimeout!
        server_done_event.wait(5)
        server_cancelled_mock.assert_called_once()


async def test_middleware_emits_499_when_client_disconnects_before_response():
    # When the client disconnects while the handler is still running (and no
    # response has been sent yet), the middleware must emit a synthetic 499
    # response so that outer middlewares observe a real response instead of
    # raising RuntimeError("No response returned").

    async def _never_responding_app(scope: Scope, receive: Receive, send: Send) -> None:
        # Simulates a handler still working when the client disconnects
        await asyncio.Event().wait()

    middleware = RequestCancellationMiddleware(_never_responding_app)

    sent_messages: list[Message] = []
    initial_request_sent = False

    async def _receive() -> Message:
        nonlocal initial_request_sent
        if not initial_request_sent:
            initial_request_sent = True
            return {"type": "http.request", "body": b"", "more_body": False}
        return {"type": "http.disconnect"}

    async def _send(message: Message) -> None:
        sent_messages.append(message)

    scope: Scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/",
        "raw_path": b"/",
        "query_string": b"",
        "root_path": "",
        "headers": [],
        "server": ("127.0.0.1", 8000),
        "client": ("127.0.0.1", 12345),
    }

    await asyncio.wait_for(middleware(scope, _receive, _send), timeout=5)

    start_messages = [m for m in sent_messages if m["type"] == "http.response.start"]
    assert len(start_messages) == 1
    assert start_messages[0]["status"] == 499

    body_messages = [m for m in sent_messages if m["type"] == "http.response.body"]
    assert len(body_messages) == 1


async def test_middleware_does_not_inject_499_when_client_disconnects_mid_stream():
    # When the client disconnects AFTER the response has already started
    # streaming, the middleware must NOT inject a second http.response.start
    # (which would violate the ASGI protocol). The already-committed status is
    # preserved and the truncated stream simply ends.

    streaming_started = asyncio.Event()

    async def _streaming_app(scope: Scope, receive: Receive, send: Send) -> None:
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"chunk", "more_body": True})
        streaming_started.set()
        # still streaming when the client disconnects
        await asyncio.Event().wait()

    middleware = RequestCancellationMiddleware(_streaming_app)

    sent_messages: list[Message] = []
    initial_request_sent = False

    async def _receive() -> Message:
        nonlocal initial_request_sent
        if not initial_request_sent:
            initial_request_sent = True
            return {"type": "http.request", "body": b"", "more_body": False}
        # only signal the disconnect once the response is actually streaming
        await streaming_started.wait()
        return {"type": "http.disconnect"}

    async def _send(message: Message) -> None:
        sent_messages.append(message)

    scope: Scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/",
        "raw_path": b"/",
        "query_string": b"",
        "root_path": "",
        "headers": [],
        "server": ("127.0.0.1", 8000),
        "client": ("127.0.0.1", 12345),
    }

    # must complete without raising (no protocol violation, no leaked error)
    await asyncio.wait_for(middleware(scope, _receive, _send), timeout=5)

    start_messages = [m for m in sent_messages if m["type"] == "http.response.start"]
    # exactly one start, with the status the handler already committed (NOT 499)
    assert len(start_messages) == 1
    assert start_messages[0]["status"] == 200
