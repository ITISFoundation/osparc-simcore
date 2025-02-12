import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack
from typing import Final

import aiodocker
import aiohttp
import tenacity
from aiohttp import ClientSession
from fastapi import FastAPI
from fastapi_lifespan_manager import State
from pydantic import NonNegativeInt
from servicelib.fastapi.lifespan_utils import LifespanGenerator
from settings_library.docker_api_proxy import DockerApiProxysettings

_logger = logging.getLogger(__name__)

_DEFAULT_DOCKER_API_PROXY_HEALTH_TIMEOUT: Final[NonNegativeInt] = 5


def get_lifespan_remote_docker_client(
    settings: DockerApiProxysettings,
) -> LifespanGenerator:
    async def _(app: FastAPI) -> AsyncIterator[State]:

        session: ClientSession | None = None
        if settings.DOCKER_API_PROXY_USER and settings.DOCKER_API_PROXY_PASSWORD:
            session = ClientSession(
                auth=aiohttp.BasicAuth(
                    login=settings.DOCKER_API_PROXY_USER,
                    password=settings.DOCKER_API_PROXY_PASSWORD.get_secret_value(),
                )
            )

        async with AsyncExitStack() as exit_stack:
            if settings.DOCKER_API_PROXY_USER and settings.DOCKER_API_PROXY_PASSWORD:
                await exit_stack.enter_async_context(
                    ClientSession(
                        auth=aiohttp.BasicAuth(
                            login=settings.DOCKER_API_PROXY_USER,
                            password=settings.DOCKER_API_PROXY_PASSWORD.get_secret_value(),
                        )
                    )
                )

            client = await exit_stack.enter_async_context(
                aiodocker.Docker(url=settings.base_url, session=session)
            )

            app.state.remote_docker_client = client

            await wait_till_docker_api_proxy_is_responsive(app)

            # NOTE this has to be inside exit_stack scope
            yield {}

    return _


@tenacity.retry(
    wait=tenacity.wait_fixed(5),
    stop=tenacity.stop_after_delay(60),
    before_sleep=tenacity.before_sleep_log(_logger, logging.WARNING),
    reraise=True,
)
async def wait_till_docker_api_proxy_is_responsive(app: FastAPI) -> None:
    await is_docker_api_proxy_ready(app)


async def is_docker_api_proxy_ready(
    app: FastAPI, *, timeout=_DEFAULT_DOCKER_API_PROXY_HEALTH_TIMEOUT  # noqa: ASYNC109
) -> bool:
    try:
        await asyncio.wait_for(get_remote_docker_client(app).version(), timeout=timeout)
    except (aiodocker.DockerError, TimeoutError):
        return False
    return True


def get_remote_docker_client(app: FastAPI) -> aiodocker.Docker:
    assert isinstance(app.state.remote_docker_client, aiodocker.Docker)  # nosec
    return app.state.remote_docker_client
