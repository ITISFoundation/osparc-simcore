import contextlib
import logging
from typing import cast

from fastapi import FastAPI
from servicelib.logging_utils import log_catch
from servicelib.redis import RedisClientSDK
from settings_library.redis import RedisSettings
from tenacity._asyncio import AsyncRetrying
from tenacity.before_sleep import before_sleep_log
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_random_exponential

from ..core.errors import ConfigurationError, RedisNotConnectedError

logger = logging.getLogger(__name__)


def setup(app: FastAPI) -> None:
    async def on_startup() -> None:
        app.state.redis = None
        settings: RedisSettings = app.state.settings.AUTOSCALING_REDIS
        app.state.redis = client = RedisClientSDK(settings.dsn_locks)
        async for attempt in AsyncRetrying(
            reraise=True,
            stop=stop_after_delay(120),
            wait=wait_random_exponential(max=30),
            before_sleep=before_sleep_log(logger, logging.WARNING),
        ):
            with attempt:
                connected = await client.ping()
                if not connected:
                    raise RedisNotConnectedError(dsn=settings.dsn_locks)

    async def on_shutdown() -> None:
        if app.state.rabbitmq_client:
            await app.state.rabbitmq_client.close()

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)


def get_rabbitmq_client(app: FastAPI) -> RabbitMQClient:
    if not app.state.rabbitmq_client:
        raise ConfigurationError(
            msg="RabbitMQ client is not available. Please check the configuration."
        )
    return cast(RabbitMQClient, app.state.rabbitmq_client)


async def post_message(app: FastAPI, message: RabbitMessageBase) -> None:
    with log_catch(logger, reraise=False), contextlib.suppress(ConfigurationError):
        # NOTE: if rabbitmq was not initialized the error does not need to flood the logs
        await get_rabbitmq_client(app).publish(message.channel_name, message.json())
