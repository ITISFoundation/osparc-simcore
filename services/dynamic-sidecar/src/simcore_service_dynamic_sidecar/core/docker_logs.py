"""
    BackgroundLogFetcher:
        Creates background task that
        reads every line of a container's log and
        posts it as a message to rabbit's log channel (logger)
"""


import logging
from asyncio import CancelledError, Task, create_task
from contextlib import suppress
from typing import Any, Callable, Coroutine, Optional, cast

from fastapi import FastAPI

from .docker_utils import docker_client
from .rabbitmq import RabbitMQ

logger = logging.getLogger(__name__)


async def _logs_fetcher_worker(
    container_name: str, dispatch_log: Callable[..., Coroutine[Any, Any, None]]
) -> None:
    logger.info("Started log fetching for container %s", container_name)

    async with docker_client() as docker:
        container = await docker.containers.get(container_name)

        # extact image to display in logs, Eg: from
        # registry:5000/simcore/services/dynamic/dy-static-file-server-dynamic-sidecar:2.0.2
        # "dy-static-file-server-dynamic-sidecar:2.0.2"
        container_inspect = await container.show()
        image_name = container_inspect["Config"]["Image"].split("/")[-1]

        logger.debug("Streaming logs from %s, image %s", container_name, image_name)
        async for line in container.log(stdout=True, stderr=True, follow=True):
            await dispatch_log(image_name=image_name, message=line)


class BackgroundLogFetcher:
    def __init__(self, app: FastAPI) -> None:
        # requires rabbitmq to be in place
        assert app.state.rabbitmq  # nosec

        self._app: FastAPI = app

        self._log_processor_tasks: dict[str, Task[None]] = {}

    @property
    def rabbitmq(self) -> RabbitMQ:
        return self._app.state.rabbitmq  # type: ignore

    async def _dispatch_logs(self, image_name: str, message: str) -> None:
        # sending the logs to the UI to facilitate the
        # user debugging process
        await self.rabbitmq.post_log_message(f"[{image_name}] {message}")

    async def start_log_feching(self, container_name: str) -> None:
        self._log_processor_tasks[container_name] = create_task(
            _logs_fetcher_worker(
                container_name=container_name, dispatch_log=self._dispatch_logs
            ),
            name=f"rabbitmq_log_processor_tasks/{container_name}",
        )

        logger.info("Subscribed to fetch logs from '%s'", container_name)

    async def stop_log_fetching(self, container_name: str) -> None:
        logger.debug("Stopping logs fetching from container '%s'", container_name)

        task = self._log_processor_tasks.pop(container_name)
        task.cancel()
        with suppress(CancelledError):
            await task

        logger.debug("Logs fetching stopped for container '%s'", container_name)

    async def stop_fetcher(self) -> None:
        for container_name in list(self._log_processor_tasks.keys()):
            await self.stop_log_fetching(container_name)


def _get_background_log_fetcher(app: FastAPI) -> Optional[BackgroundLogFetcher]:
    if hasattr(app.state, "background_log_fetcher"):
        return cast(BackgroundLogFetcher, app.state.background_log_fetcher)
    return None


async def start_log_fetching(app: FastAPI, container_name: str) -> None:
    """start fetching logs from service"""
    background_log_fetcher = _get_background_log_fetcher(app)
    if background_log_fetcher is not None:
        await background_log_fetcher.start_log_feching(container_name)


async def stop_log_fetching(app: FastAPI, container_name: str) -> None:
    """stop fetching logs from service"""
    background_log_fetcher = _get_background_log_fetcher(app)
    if background_log_fetcher is not None:
        await background_log_fetcher.stop_log_fetching(container_name)


def setup_background_log_fetcher(app: FastAPI) -> None:
    async def on_startup() -> None:
        app.state.background_log_fetcher = BackgroundLogFetcher(app)

        logger.info("Started background container log fetcher")

    async def on_shutdown() -> None:
        if app.state.background_log_fetcher is None:
            logger.warning("No background_log_fetcher to stop")
            return

        await app.state.background_log_fetcher.stop_fetcher()
        logger.info("stopped background container log fetcher")

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)
