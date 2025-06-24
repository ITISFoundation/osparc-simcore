import asyncio
import logging
import threading
from asyncio import AbstractEventLoop
from collections.abc import Awaitable
from typing import Final

import distributed
from common_library.async_tools import cancel_and_wait
from servicelib.logging_utils import log_catch, log_context
from servicelib.rabbitmq import RabbitMQClient, wait_till_rabbitmq_responsive
from servicelib.rabbitmq._models import RabbitMessage
from settings_library.rabbit import RabbitSettings

from .errors import ConfigurationError

_logger = logging.getLogger(__name__)

_RABBITMQ_CONFIGURATION_ERROR: Final[str] = (
    "RabbitMQ client is not available. Please check the configuration."
)


class RabbitMQPlugin(distributed.WorkerPlugin):
    """Dask Worker Plugin for RabbitMQ integration"""

    name = "rabbitmq_worker_plugin"
    _main_thread_loop: AbstractEventLoop | None = None
    _client: RabbitMQClient | None = None
    _settings: RabbitSettings | None = None
    _message_queue: asyncio.Queue | None = None
    _message_processor: asyncio.Task | None = None

    def __init__(self, settings: RabbitSettings):
        self._settings = settings

    async def _process_messages(self) -> None:
        """Process messages from worker threads in the main thread"""
        assert self._message_queue is not None  # nosec
        assert self._client is not None  # nosec

        with log_context(_logger, logging.INFO, "RabbitMQ message processor"):
            while True:
                with log_catch(_logger, reraise=False):
                    exchange_name, message_data = await self._message_queue.get()
                    try:
                        await self._client.publish(exchange_name, message_data)
                    finally:
                        self._message_queue.task_done()

    def setup(self, worker: distributed.Worker) -> Awaitable[None]:
        """Called when the plugin is attached to a worker"""

        async def _() -> None:
            if not self._settings:
                _logger.warning(
                    "RabbitMQ client is de-activated (no settings provided)"
                )
                return

            if threading.current_thread() is not threading.main_thread():
                _logger.warning(
                    "RabbitMQ client plugin setup is not in the main thread! TIP: if in pytest it's ok."
                )

            with log_context(
                _logger,
                logging.INFO,
                f"RabbitMQ client initialization for worker {worker.address}",
            ):
                self._main_thread_loop = asyncio.get_event_loop()
                await wait_till_rabbitmq_responsive(self._settings.dsn)
                self._client = RabbitMQClient(
                    client_name="dask-sidecar", settings=self._settings
                )

                self._message_queue = asyncio.Queue()
                self._message_processor = asyncio.create_task(
                    self._process_messages(), name="rabbit_message_processor"
                )

        return _()

    def teardown(self, worker: distributed.Worker) -> Awaitable[None]:
        """Called when the worker shuts down or the plugin is removed"""

        async def _() -> None:
            with log_context(
                _logger,
                logging.INFO,
                f"RabbitMQ client teardown for worker {worker.address}",
            ):
                if not self._client:
                    return
                if threading.current_thread() is threading.main_thread():
                    _logger.info(
                        "RabbitMQ client plugin setup is in the main thread! That is good."
                    )
                else:
                    _logger.warning(
                        "RabbitMQ client plugin setup is not the main thread! TIP: if in pytest it's ok."
                    )

                # Cancel the message processor task
                if self._message_processor:
                    with log_catch(_logger, reraise=False):
                        await cancel_and_wait(self._message_processor, max_delay=5)
                    self._message_processor = None

                # close client
                current_loop = asyncio.get_event_loop()
                if self._main_thread_loop != current_loop:
                    _logger.warning("RabbitMQ client is de-activated (loop mismatch)")
                assert self._main_thread_loop  # nosec
                with log_catch(_logger, reraise=False):
                    await asyncio.wait_for(self._client.close(), timeout=5.0)

                self._client = None

        return _()

    def get_client(self) -> RabbitMQClient:
        """Returns the RabbitMQ client or raises an error if not available"""
        if not self._client:
            raise ConfigurationError(msg=_RABBITMQ_CONFIGURATION_ERROR)
        return self._client

    async def publish_message_from_any_thread(
        self, exchange_name: str, message_data: RabbitMessage
    ) -> None:
        """Enqueue a message to be published to RabbitMQ from any thread"""
        assert self._message_queue  # nosec

        if threading.current_thread() is threading.main_thread():
            # If we're in the main thread, add directly to the queue
            await self._message_queue.put((exchange_name, message_data))
            return

        # If we're in a worker thread, we need to use a different approach
        assert self._main_thread_loop  # nosec

        # Create a Future in the main thread's event loop
        future = asyncio.run_coroutine_threadsafe(
            self._message_queue.put((exchange_name, message_data)),
            self._main_thread_loop,
        )

        # waiting here is quick, just queueing
        future.result()


def get_rabbitmq_client(worker: distributed.Worker) -> RabbitMQPlugin:
    """Returns the RabbitMQ client or raises an error if not available"""
    if not worker.plugins:
        raise ConfigurationError(msg=_RABBITMQ_CONFIGURATION_ERROR)
    rabbitmq_plugin = worker.plugins.get(RabbitMQPlugin.name)
    if not isinstance(rabbitmq_plugin, RabbitMQPlugin):
        raise ConfigurationError(msg=_RABBITMQ_CONFIGURATION_ERROR)
    return rabbitmq_plugin
