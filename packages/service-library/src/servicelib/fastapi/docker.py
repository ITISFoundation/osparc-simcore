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
from fastapi_lifespan_manager import LifespanManager, State
from pydantic import NonNegativeInt
from settings_library.docker_api_proxy import DockerApiProxysettings

from .lifespan_utils import PublisherLifespan, create_publisher_lifespan

_logger = logging.getLogger(__name__)

_DEFAULT_DOCKER_API_PROXY_HEALTH_TIMEOUT: Final[NonNegativeInt] = 5


_REMOTE_DOCKER_CLIENT_STATE_KEY: Final[str] = "remote_docker_client"


def _create_remote_docker_client_lifespan(settings: DockerApiProxysettings) -> PublisherLifespan:
    async def _lifespan(_app: FastAPI, _state: State) -> AsyncIterator[State]:
        async with AsyncExitStack() as exit_stack:
            session = await exit_stack.enter_async_context(
                ClientSession(
                    auth=aiohttp.BasicAuth(
                        login=settings.DOCKER_API_PROXY_USER,
                        password=settings.DOCKER_API_PROXY_PASSWORD.get_secret_value(),
                    )
                )
            )

            remote_docker_client = await exit_stack.enter_async_context(
                aiodocker.Docker(url=settings.base_url, session=session)
            )

            await wait_till_docker_api_proxy_is_responsive(remote_docker_client)

            yield {
                _REMOTE_DOCKER_CLIENT_STATE_KEY: remote_docker_client,
            }

    return _lifespan


def _create_remote_docker_lifespan_manager(
    settings: DockerApiProxysettings,
) -> LifespanManager[FastAPI]:
    remote_docker_lifespan_manager = LifespanManager()
    remote_docker_lifespan_manager.add(_create_remote_docker_client_lifespan(settings=settings))
    remote_docker_lifespan_manager.add(
        create_publisher_lifespan(
            state_key=_REMOTE_DOCKER_CLIENT_STATE_KEY,
            app_state_attr="remote_docker_client",
        )
    )
    return remote_docker_lifespan_manager


def configure_remote_docker_client(
    app_lifespan: LifespanManager[FastAPI],
    *,
    settings: DockerApiProxysettings,
) -> None:
    app_lifespan.include(_create_remote_docker_lifespan_manager(settings=settings))


@tenacity.retry(
    wait=tenacity.wait_fixed(5),
    stop=tenacity.stop_after_delay(60),
    before_sleep=tenacity.before_sleep_log(_logger, logging.WARNING),
    reraise=True,
)
async def wait_till_docker_api_proxy_is_responsive(client: aiodocker.Docker) -> None:
    await is_docker_api_proxy_ready(client)


async def is_docker_api_proxy_ready(
    client: aiodocker.Docker,
    *,
    timeout=_DEFAULT_DOCKER_API_PROXY_HEALTH_TIMEOUT,  # noqa: ASYNC109
) -> bool:
    try:
        await asyncio.wait_for(client.version(), timeout=timeout)
    except (aiodocker.DockerError, TimeoutError):
        return False
    return True


def get_remote_docker_client(app: FastAPI) -> aiodocker.Docker:
    assert isinstance(app.state.remote_docker_client, aiodocker.Docker)  # nosec
    return app.state.remote_docker_client
