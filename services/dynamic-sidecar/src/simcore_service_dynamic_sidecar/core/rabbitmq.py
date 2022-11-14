import logging
from functools import lru_cache
from typing import Union, cast

from fastapi import FastAPI
from models_library.rabbitmq_messages import (
    EventRabbitMessage,
    LoggerRabbitMessage,
    RabbitEventMessageType,
    RabbitMessageBase,
)
from servicelib.logging_utils import log_context
from servicelib.rabbitmq import RabbitMQClient
from servicelib.rabbitmq_utils import wait_till_rabbitmq_responsive

from ..core.settings import ApplicationSettings

log = logging.getLogger(__file__)


async def _post_rabbit_message(app: FastAPI, message: RabbitMessageBase) -> None:
    # NOTE: this check is necessary when the dy-sidecar is used on the CLI
    # where the rabbit is not initialized, it's not optimal but it allows
    # to run the CLI without rabbit...
    if _is_rabbitmq_initialized(app):
        await get_rabbitmq_client(app).publish(message.channel_name, message.json())


async def post_log_message(app: FastAPI, logs: Union[str, list[str]]) -> None:
    if isinstance(logs, str):
        logs = [logs]

    app_settings: ApplicationSettings = app.state.settings
    message = LoggerRabbitMessage(
        node_id=app_settings.DY_SIDECAR_NODE_ID,
        user_id=app_settings.DY_SIDECAR_USER_ID,
        project_id=app_settings.DY_SIDECAR_PROJECT_ID,
        messages=logs,
    )

    await _post_rabbit_message(app, message)


async def post_sidecar_log_message(app: FastAPI, logs: str) -> None:
    await post_log_message(app, f"[sidecar] {logs}")


async def post_event_reload_iframe(app: FastAPI) -> None:
    app_settings: ApplicationSettings = app.state.settings
    message = EventRabbitMessage(
        node_id=app_settings.DY_SIDECAR_NODE_ID,
        user_id=app_settings.DY_SIDECAR_USER_ID,
        project_id=app_settings.DY_SIDECAR_PROJECT_ID,
        action=RabbitEventMessageType.RELOAD_IFRAME,
    )
    await _post_rabbit_message(app, message)


def setup_rabbitmq(app: FastAPI) -> None:
    async def on_startup() -> None:
        app_settings: ApplicationSettings = app.state.settings
        assert app_settings.RABBIT_SETTINGS  # nosec
        settings = app_settings.RABBIT_SETTINGS
        await wait_till_rabbitmq_responsive(settings.dsn)
        with log_context(log, logging.INFO, msg="Create RabbitMQClient"):
            app.state.rabbitmq_client = RabbitMQClient(
                client_name=f"dynamic-sidecar_{app_settings.DY_SIDECAR_NODE_ID}",
                settings=settings,
            )

    async def on_shutdown() -> None:
        if app.state.rabbitmq_client:
            await app.state.rabbitmq_client.close()

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)


@lru_cache(maxsize=1)
def _is_rabbitmq_initialized(app: FastAPI) -> bool:
    return hasattr(app.state, "rabbitmq_client")


def get_rabbitmq_client(app: FastAPI) -> RabbitMQClient:
    if not _is_rabbitmq_initialized(app):
        raise RuntimeError(
            "RabbitMQ client is not available. Please check the configuration."
        )
    return cast(RabbitMQClient, app.state.rabbitmq_client)
