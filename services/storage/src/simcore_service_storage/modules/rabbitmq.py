import logging
from typing import cast

from fastapi import FastAPI
from servicelib.logging_utils import log_context
from servicelib.rabbitmq import (
    RabbitMQRPCClient,
    wait_till_rabbitmq_responsive,
)
from settings_library.rabbit import RabbitSettings

from ..exceptions.errors import ConfigurationError

_logger = logging.getLogger(__name__)


def setup(app: FastAPI) -> None:
    async def on_startup() -> None:
        with log_context(
            _logger,
            logging.INFO,
            msg="Storage startup Rabbitmq",
        ):
            rabbit_settings: RabbitSettings | None = app.state.settings.STORAGE_RABBITMQ
            if not rabbit_settings:
                raise ConfigurationError(
                    msg="RabbitMQ client is de-activated in the settings"
                )
            await wait_till_rabbitmq_responsive(rabbit_settings.dsn)
            app.state.rabbitmq_rpc_server = await RabbitMQRPCClient.create(
                client_name="storage_rpc_server", settings=rabbit_settings
            )

    async def on_shutdown() -> None:
        with log_context(
            _logger,
            logging.INFO,
            msg="Storage shutdown Rabbitmq",
        ):
            if app.state.rabbitmq_rpc_server:
                await app.state.rabbitmq_rpc_server.close()

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)


def get_rabbitmq_rpc_server(app: FastAPI) -> RabbitMQRPCClient:
    assert app.state.rabbitmq_rpc_server  # nosec
    return cast(RabbitMQRPCClient, app.state.rabbitmq_rpc_server)
