import logging

import distributed
from models_library.rabbitmq_messages import RabbitMessageBase
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
        _logger.info("Setting up RabbitMQ plugin")
        if not self._settings:
            _logger.warning("RabbitMQ client is de-activated (no settings provided)")
            return

        await wait_till_rabbitmq_responsive(self._settings.dsn)
        self._client = RabbitMQClient(
            client_name="dask-sidecar", settings=self._settings
        )
        _logger.info("RabbitMQ client initialized successfully")

    async def teardown(self, worker: distributed.Worker) -> None:
        """Called when the worker shuts down or the plugin is removed"""
        _logger.info("Tearing down RabbitMQ plugin")
        if self._client:
            await self._client.close()
            self._client = None
            _logger.info("RabbitMQ client closed")

    def get_client(self) -> RabbitMQClient:
        """Returns the RabbitMQ client or raises an error if not available"""
        if not self._client:
            raise ConfigurationError(
                msg="RabbitMQ client is not available. Please check the configuration."
            )
        return self._client

    async def publish(self, channel_name: str, message: RabbitMessageBase) -> None:
        """Publishes a message to the specified channel"""
        if self._client:
            await self._client.publish(channel_name, message)


# async def on_startup(
#     worker: distributed.Worker, rabbit_settings: RabbitSettings
# ) -> None:
#     worker.rabbitmq_client = None
#     settings: RabbitSettings | None = rabbit_settings
#     if not settings:
#         __logger.warning("Rabbit MQ client is de-activated in the settings")
#         return
#     await wait_till_rabbitmq_responsive(settings.dsn)
#     worker.rabbitmq_client = RabbitMQClient(
#         client_name="dask-sidecar", settings=settings
#     )


# async def on_shutdown(worker: distributed.Worker) -> None:
#     if worker.rabbitmq_client:
#         await worker.rabbitmq_client.close()


# def get_rabbitmq_client(worker: distributed.Worker) -> RabbitMQClient:
#     if not worker.rabbitmq_client:
#         raise ConfigurationError(
#             msg="RabbitMQ client is not available. Please check the configuration."
#         )
#     return cast(RabbitMQClient, worker.rabbitmq_client)


# async def post_message(worker: distributed.Worker, message: RabbitMessageBase) -> None:
#     with log_catch(__logger, reraise=False), contextlib.suppress(ConfigurationError):
#         # NOTE: if rabbitmq was not initialized the error does not need to flood the logs
#         await get_rabbitmq_client(worker).publish(message.channel_name, message)
