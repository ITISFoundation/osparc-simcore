import logging
from collections.abc import Awaitable

import distributed
from servicelib.logging_utils import log_context
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

    def setup(self, worker: distributed.Worker) -> Awaitable[None]:
        """Called when the plugin is attached to a worker"""

        async def _() -> None:
            if not self._settings:
                _logger.warning(
                    "RabbitMQ client is de-activated (no settings provided)"
                )
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

        return _()

    def teardown(self, worker: distributed.Worker) -> Awaitable[None]:
        """Called when the worker shuts down or the plugin is removed"""

        async def _() -> None:
            with log_context(
                _logger,
                logging.INFO,
                f"RabbitMQ client teardown for worker {worker.address}",
            ):
                if self._client:
                    await self._client.close()
                    self._client = None

        return _()

    def get_client(self) -> RabbitMQClient:
        """Returns the RabbitMQ client or raises an error if not available"""
        if not self._client:
            raise ConfigurationError(
                msg="RabbitMQ client is not available. Please check the configuration."
            )
        return self._client


def get_rabbitmq_client(worker: distributed.Worker) -> RabbitMQClient:
    """Returns the RabbitMQ client or raises an error if not available"""
    if not worker.plugins:
        raise ConfigurationError(
            msg="RabbitMQ client is not available. Please check the configuration."
        )
    rabbitmq_plugin = worker.plugins.get(RabbitMQPlugin.name)
    if not isinstance(rabbitmq_plugin, RabbitMQPlugin):
        raise ConfigurationError(
            msg="RabbitMQ client is not available. Please check the configuration."
        )
    return rabbitmq_plugin.get_client()
