import logging
from asyncio import CancelledError, Task, create_task
from contextlib import suppress
from typing import Any, Callable, Coroutine, Dict, Optional, cast

from fastapi import FastAPI

from .rabbitmq import RabbitMQ
from .settings import DynamicSidecarSettings
from .utils import docker_client

logger = logging.getLogger(__name__)


async def _logs_fetcher_worker(
    container_name: str, dispatch_log: Callable[..., Coroutine[Any, Any, None]]
) -> None:
    logger.info("Started log fetching for container %s", container_name)
    async with docker_client() as docker:
        container = await docker.containers.get(container_name)

        logger.debug("Streaming logs from %s", container_name)
        async for line in container.log(stdout=True, stderr=True, follow=True):
            await dispatch_log(container_name=container_name, message=line)


def _setup_logger(container_name: str) -> None:
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(
        logging.Formatter("[%(levelname)-4s:%(name)-20s] %(message)s")
    )
    container_logger = logging.getLogger(container_name)
    container_logger.addHandler(stream_handler)


class BackgroundLogFetcher:
    def __init__(self, app: FastAPI) -> None:
        self._settings: DynamicSidecarSettings = app.state.settings
        self._log_processor_tasks: Dict[str, Task[None]] = {}

        self.rabbit_mq: RabbitMQ = RabbitMQ(
            rabbit_settings=self._settings.RABBIT_SETTINGS
        )

    async def start_fetcher(self) -> None:
        await self.rabbit_mq.connect()

    async def _dispatch_logs(self, container_name: str, message: str) -> None:
        # logs from the containers will be logged at warning level to
        # make sure they are not lost in production environments
        # as these are very important to debug issues from users
        logging.getLogger(container_name).warning(message)

        # sending the logs to the UI to facilitate the
        # user debugging process
        await self.rabbit_mq.post_log_message(
            user_id=self._settings.DY_SIDECAR_USER_ID,
            project_id=self._settings.DY_SIDECAR_PROJECT_ID,
            node_id=self._settings.DY_SIDECAR_NODE_ID,
            log_msg=f"[{container_name}] {message}",
        )

    async def start_log_feching(self, container_name: str) -> None:
        self._log_processor_tasks[container_name] = create_task(
            _logs_fetcher_worker(
                container_name=container_name, dispatch_log=self._dispatch_logs
            )
        )
        _setup_logger(container_name)

        logger.debug("Subscribed to fetch logs from '%s'", container_name)

    async def stop_log_fetching(self, container_name: str) -> None:
        logger.debug("Stopping logs fetching from container '%s'", container_name)
        task = self._log_processor_tasks[container_name]
        with suppress(CancelledError):
            task.cancel()
            await task
        del self._log_processor_tasks[container_name]
        logger.debug("Logs fetching stopped for container '%s'", container_name)

    async def stop_fetcher(self) -> None:
        for container_name in list(self._log_processor_tasks.keys()):
            await self.stop_log_fetching(container_name)
        await self.rabbit_mq.close()


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

        await app.state.background_log_fetcher.start_fetcher()
        logger.info("Started background container log fetcher")

    async def on_shutdown() -> None:
        if app.state.background_log_fetcher is None:
            logger.warning("No background_log_fetcher to stop")
            return

        await app.state.background_log_fetcher.stop_fetcher()
        logger.info("stopped background container log fetcher")

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)
