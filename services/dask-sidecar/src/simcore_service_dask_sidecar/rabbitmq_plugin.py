import logging

import distributed
from models_library.rabbitmq_messages import RabbitMessageBase
from servicelib.logging_utils import log_catch, log_context
from servicelib.rabbitmq import RabbitMQClient, wait_till_rabbitmq_responsive
from settings_library.rabbit import RabbitSettings

from .errors import ConfigurationError

_logger = logging.getLogger(__name__)


class RabbitMQPlugin(distributed.WorkerPlugin):
    """Dask Worker Plugin for RabbitMQ integration"""

    name = "rabbitmq_plugin"
    _client: RabbitMQClient | None = None
    _settings: RabbitSettings | None = None

    def __init__(self, settings: RabbitSettings):
        self._settings = settings

    async def setup(self, worker: distributed.Worker) -> None:
        """Called when the plugin is attached to a worker"""
        if not self._settings:
            _logger.warning("RabbitMQ client is de-activated (no settings provided)")
            return

        with log_context(
            _logger,
            logging.INFO,
            f"RabbitMQ client initialization for worker {worker.address}",
        ):
            await wait_till_rabbitmq_responsive(self._settings.dsn)
            self._client = RabbitMQClient(
                client_name="dask-sidecar", settings=self._settings
            )

    async def teardown(self, worker: distributed.Worker) -> None:
        """Called when the worker shuts down or the plugin is removed"""
        with log_context(
            _logger,
            logging.INFO,
            f"RabbitMQ client teardown for worker {worker.address}",
        ):
            if self._client:
                await self._client.close()
                self._client = None

    def get_client(self) -> RabbitMQClient:
        """Returns the RabbitMQ client or raises an error if not available"""
        if not self._client:
            raise ConfigurationError(
                msg="RabbitMQ client is not available. Please check the configuration."
            )
        return self._client

    async def publish(self, *, channel_name: str, message: RabbitMessageBase) -> None:
        """Publishes a message to the specified channel"""
        with log_catch(_logger, reraise=False):
            if self._client:
                await self._client.publish(channel_name, message)
