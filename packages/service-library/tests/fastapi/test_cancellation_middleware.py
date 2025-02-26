import asyncio
import logging
from collections.abc import Iterator
from threading import Thread
from unittest.mock import Mock

import httpx
import pytest
import uvicorn
from fastapi import APIRouter, FastAPI
from pytest_simcore.helpers.logging_tools import log_context
from servicelib.fastapi.cancellation_middleware import CancellationMiddleware
from servicelib.utils import unused_port
from yarl import URL


@pytest.fixture
def server_done_event() -> asyncio.Event:
    return asyncio.Event()


@pytest.fixture
def server_cancelled_mock() -> Mock:
    return Mock()


@pytest.fixture
def fastapi_router(
    server_done_event: asyncio.Event, server_cancelled_mock: Mock
) -> APIRouter:
    router = APIRouter()

    @router.get("/sleep")
    async def sleep(sleep_time: float) -> dict[str, str]:
        with log_context(logging.INFO, msg="sleeper") as ctx:
            try:
                await asyncio.sleep(sleep_time)
                return {"message": f"Slept for {sleep_time} seconds"}
            except asyncio.CancelledError:
                ctx.logger.info("sleeper cancelled!")
                server_cancelled_mock()
                return {"message": "Cancelled"}
            finally:
                server_done_event.set()

    return router


@pytest.fixture
def fastapi_app(fastapi_router: APIRouter) -> FastAPI:
    app = FastAPI()
    app.include_router(fastapi_router)
    app.add_middleware(CancellationMiddleware)
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

        ctx.logger.info(
            "server ready at: %s",
            f"http://127.0.0.1:{random_port}",
        )

        yield URL(f"http://127.0.0.1:{random_port}")

        server.should_exit = True
        thread.join(timeout=10)


async def test_server_cancels_when_client_disconnects(
    uvicorn_server: URL, server_done_event: asyncio.Event, server_cancelled_mock: Mock
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

        async with asyncio.timeout(10):
            await server_done_event.wait()
        server_cancelled_mock.assert_called_once()
