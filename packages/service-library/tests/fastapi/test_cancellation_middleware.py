import asyncio
import logging
from collections.abc import Iterator
from threading import Thread

import httpx
import pytest
import uvicorn
from fastapi import APIRouter, FastAPI
from pytest_simcore.helpers.logging_tools import log_context
from servicelib.fastapi.cancellation_middleware import CancellationMiddleware
from servicelib.utils import unused_port
from yarl import URL

router = APIRouter()


@router.get("/normal")
async def normal_endpoint():
    await asyncio.sleep(2)
    return {"message": "Normal response"}


@pytest.fixture(scope="module")
def fastapi_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    app.add_middleware(CancellationMiddleware)
    return app


@pytest.fixture(scope="module")
def uvicorn_server(
    fastapi_app: FastAPI,
    # app_environment: EnvVarsDict,
) -> Iterator[URL]:
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


async def test_normal_mode(uvicorn_server: URL):
    async with httpx.AsyncClient(base_url=f"{uvicorn_server}") as client:
        response = await client.get("/normal")
        assert response.status_code == 200
        assert response.json() == {"message": "Normal response"}


async def test_client_disconnects(uvicorn_server: URL):
    # with pytest.raises(Exception) as excinfo:
    async with httpx.AsyncClient(base_url=f"{uvicorn_server}") as client:
        with pytest.raises(httpx.ReadTimeout):
            await client.get("/normal", timeout=0.1)
    # assert "Client disconnected" in str(excinfo.value)
