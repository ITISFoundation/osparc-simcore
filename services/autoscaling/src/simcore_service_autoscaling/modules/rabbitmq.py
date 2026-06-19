import contextlib
import logging
from typing import cast

from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager
from models_library.rabbitmq_messages import RabbitMessageBase
from servicelib.fastapi.rabbitmq_lifespan import configure_rabbitmq_client as _configure_rabbitmq_client
from servicelib.logging_utils import log_catch
from servicelib.rabbitmq import RabbitMQClient
from settings_library.rabbit import RabbitSettings

from ..core.errors import ConfigurationError

logger = logging.getLogger(__name__)


def configure_rabbitmq_client(
    app_lifespan: LifespanManager[FastAPI],
    *,
    settings: RabbitSettings | None,
) -> None:
    _configure_rabbitmq_client(
        app_lifespan,
        settings=settings,
        client_name="autoscaling",
    )


def get_rabbitmq_client(app: FastAPI) -> RabbitMQClient:
    if not hasattr(app.state, "rabbitmq_client") or not app.state.rabbitmq_client:
        msg = "RabbitMQ client is not available. Please check the configuration."
        raise ConfigurationError(msg=msg)
    return cast(RabbitMQClient, app.state.rabbitmq_client)


async def post_message(app: FastAPI, message: RabbitMessageBase) -> None:
    with log_catch(logger, reraise=False), contextlib.suppress(ConfigurationError):
        # NOTE: if rabbitmq was not initialized the error does not need to flood the logs
        await get_rabbitmq_client(app).publish(message.channel_name, message)
