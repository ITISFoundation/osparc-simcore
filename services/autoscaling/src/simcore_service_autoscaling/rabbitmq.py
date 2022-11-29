import logging
from typing import Optional, cast

from fastapi import FastAPI
from models_library.rabbitmq_messages import RabbitClusterStateMessage
from servicelib.rabbitmq import RabbitMQClient
from servicelib.rabbitmq_utils import wait_till_rabbitmq_responsive
from settings_library.rabbit import RabbitSettings

from .core.errors import ConfigurationError

logger = logging.getLogger(__name__)


def setup(app: FastAPI) -> None:
    async def on_startup() -> None:
        app.state.rabbitmq_client = None
        settings: Optional[RabbitSettings] = app.state.settings.AUTOSCALING_RABBITMQ
        if not settings:
            logger.warning("Rabbit MQ client is de-activated in the settings")
            return
        await wait_till_rabbitmq_responsive(settings.dsn)
        app.state.rabbitmq_client = RabbitMQClient(
            client_name="autoscaling", settings=settings
        )

    async def on_shutdown() -> None:
        if app.state.rabbitmq_client:
            await app.state.rabbitmq_client.close()

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)


async def post_cluster_state_message(
    app: FastAPI, state_msg: RabbitClusterStateMessage
) -> None:
    await get_rabbitmq_client(app).publish(state_msg.channel_name, state_msg.json())


def get_rabbitmq_client(app: FastAPI) -> RabbitMQClient:
    if not hasattr(app.state, "rabbitmq_client"):
        raise ConfigurationError(
            msg="RabbitMQ client is not available. Please check the configuration."
        )
    return cast(RabbitMQClient, app.state.rabbitmq_client)
