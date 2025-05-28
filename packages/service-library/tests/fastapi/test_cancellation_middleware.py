# pylint: disable=redefined-outer-name

import asyncio
import logging
from collections.abc import Iterator
from threading import Thread
from unittest.mock import AsyncMock

import httpx
import pytest
import uvicorn
from fastapi import APIRouter, BackgroundTasks, FastAPI
from pytest_simcore.helpers.logging_tools import log_context
from servicelib.fastapi.cancellation_middleware import RequestCancellationMiddleware
from servicelib.utils import unused_port
from tenacity import retry, stop_after_delay, wait_fixed
from yarl import URL


@pytest.fixture
def server_done_event() -> asyncio.Event:
    return asyncio.Event()


@pytest.fixture
def server_cancelled_mock() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def fastapi_router(
    server_done_event: asyncio.Event, server_cancelled_mock: AsyncMock
) -> APIRouter:
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
    async def sleep_with_background_task(
        sleep_time: float, background_tasks: BackgroundTasks
    ) -> dict[str, str]:
        with log_context(logging.INFO, msg="sleeper with background task"):
            background_tasks.add_task(_sleep_in_the_back, sleep_time)
            return {"message": "Sleeping in the back"}

    return router


@pytest.fixture
def fastapi_app(fastapi_router: APIRouter) -> FastAPI:
    app = FastAPI()
    app.include_router(fastapi_router)
    app.add_middleware(RequestCancellationMiddleware)
    return app


@pytest.fixture
def uvicorn_server(fastapi_app: FastAPI) -> Iterator[URL]:
    random_port = unused_port()
    with log_context(
        logging.INFO,
        msg=f"with uvicorn server on 127.0.0.1:{random_port}",
    ) as ctx:
        config = uvicorn.Config(
            fastapi_app,
            host="127.0.0.1",
            port=random_port,
            log_level="error",
        )
        server = uvicorn.Server(config)

        thread = Thread(target=server.run)
        thread.daemon = True
        thread.start()

        @retry(wait=wait_fixed(0.1), stop=stop_after_delay(10), reraise=True)
        def wait_for_server_ready() -> None:
            with httpx.Client() as client:
                response = client.get(f"http://127.0.1:{random_port}/")
                assert (
                    response.is_success
                ), f"Server did not start successfully: {response.status_code} {response.text}"

        wait_for_server_ready()

        ctx.logger.info(
            "server ready at: %s",
            f"http://127.0.0.1:{random_port}",
        )

        yield URL(f"http://127.0.0.1:{random_port}")

        server.should_exit = True
        thread.join(timeout=10)


async def test_server_cancels_when_client_disconnects(
    uvicorn_server: URL,
    server_done_event: asyncio.Event,
    server_cancelled_mock: AsyncMock,
):
    async with httpx.AsyncClient(base_url=f"{uvicorn_server}") as client:
        # check standard call still complete as expected
        with log_context(logging.INFO, msg="client calling endpoint"):
            response = await client.get("/sleep", params={"sleep_time": 0.1})
        assert response.status_code == 200
        assert response.json() == {"message": "Slept for 0.1 seconds"}
        async with asyncio.timeout(10):
            await server_done_event.wait()
        server_done_event.clear()

        # check slow call get cancelled
        with log_context(
            logging.INFO, msg="client calling endpoint for cancellation"
        ) as ctx:
            with pytest.raises(httpx.ReadTimeout):
                response = await client.get(
                    "/sleep", params={"sleep_time": 10}, timeout=0.1
                )
            ctx.logger.info("client disconnected from server")

        async with asyncio.timeout(5):
            await server_done_event.wait()
        server_cancelled_mock.assert_called_once()
        server_cancelled_mock.reset_mock()
        server_done_event.clear()

        # NOTE: shows that FastAPI BackgroundTasks get cancelled too!
        # check background tasks get cancelled as well sadly
        with log_context(logging.INFO, msg="client calling endpoint for cancellation"):
            response = await client.get(
                "/sleep-with-background-task",
                params={"sleep_time": 2},
            )
            assert response.status_code == 200
        async with asyncio.timeout(5):
            await server_done_event.wait()
        server_cancelled_mock.assert_called_once()
