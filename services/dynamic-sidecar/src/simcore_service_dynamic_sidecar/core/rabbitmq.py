import logging
from dataclasses import dataclass
from typing import Union

from fastapi import FastAPI
from models_library.rabbitmq_messages import (
    EventRabbitMessage,
    LoggerRabbitMessage,
    RabbitEventMessageType,
)
from servicelib.logging_utils import log_context
from servicelib.rabbitmq import RabbitMQClient as BaseRabbitMQClient

from ..core.settings import ApplicationSettings

log = logging.getLogger(__file__)


@dataclass
class RabbitMQ(BaseRabbitMQClient):
    app_settings: ApplicationSettings

    async def post_log_message(self, log_msg: Union[str, list[str]]) -> None:
        if isinstance(log_msg, str):
            log_msg = [log_msg]

        data = LoggerRabbitMessage(
            node_id=self.app_settings.DY_SIDECAR_NODE_ID,
            user_id=self.app_settings.DY_SIDECAR_USER_ID,
            project_id=self.app_settings.DY_SIDECAR_PROJECT_ID,
            messages=log_msg,
        )

        await self.publish(self.settings.RABBIT_CHANNELS["log"], data.json())

    async def send_event_reload_iframe(self) -> None:
        data = EventRabbitMessage(
            node_id=self.app_settings.DY_SIDECAR_NODE_ID,
            user_id=self.app_settings.DY_SIDECAR_USER_ID,
            project_id=self.app_settings.DY_SIDECAR_PROJECT_ID,
            action=RabbitEventMessageType.RELOAD_IFRAME,
        )
        await self.publish(self.settings.RABBIT_CHANNELS["events"], data.json())


async def send_message(rabbitmq: RabbitMQ, msg: str) -> None:
    log.debug(msg)
    await rabbitmq.post_log_message(f"[sidecar] {msg}")


def setup_rabbitmq(app: FastAPI) -> None:
    async def on_startup() -> None:
        settings: ApplicationSettings = app.state.settings
        assert settings.RABBIT_SETTINGS  # nosec
        with log_context(log, logging.INFO, msg="Connect to RabbitMQ"):
            app.state.rabbitmq = RabbitMQ(
                app_settings=settings,
                client_name=f"dynamic-sidecar_{settings.DY_SIDECAR_NODE_ID}",
                settings=settings.RABBIT_SETTINGS,
            )

    async def on_shutdown() -> None:
        if app.state.rabbitmq:
            await app.state.rabbitmq.close()

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)
