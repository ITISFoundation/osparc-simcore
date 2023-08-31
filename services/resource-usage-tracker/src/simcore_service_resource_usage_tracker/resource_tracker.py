import functools
import logging
from collections.abc import Awaitable, Callable

from fastapi import FastAPI
from models_library.rabbitmq_messages import RabbitResourceTrackingBaseMessage
from servicelib.logging_utils import log_catch, log_context
from servicelib.rabbitmq import RabbitMQClient
from settings_library.rabbit import RabbitSettings

from .core.settings import ApplicationSettings
from .modules.rabbitmq import get_rabbitmq_client
from .resource_tracker_process_messages import process_message

_logger = logging.getLogger(__name__)


async def _subscribe_to_rabbitmq(app) -> str:
    with log_context(_logger, logging.INFO, msg="Subscribing to rabbitmq channel"):
        rabbit_client: RabbitMQClient = get_rabbitmq_client(app)
        subscribed_queue: str = await rabbit_client.subscribe(
            RabbitResourceTrackingBaseMessage.get_channel_name(),
            message_handler=functools.partial(process_message, app),
            exclusive_queue=False,
        )
        return subscribed_queue


async def _unsubscribe_from_rabbitmq(app) -> None:
    with log_context(
        _logger, logging.INFO, msg="Unsubscribing from rabbitmq channels"
    ), log_catch(_logger, reraise=False):
        rabbit_client: RabbitMQClient = get_rabbitmq_client(app)
        await rabbit_client.unsubscribe(app.state.resource_tracker_rabbitmq_consumer)


def on_app_startup(app: FastAPI) -> Callable[[], Awaitable[None]]:
    async def _startup() -> None:
        with log_context(
            _logger, logging.INFO, msg="setup resource tracker"
        ), log_catch(_logger, reraise=False):
            app_settings: ApplicationSettings = app.state.settings
            app.state.resource_tracker_rabbitmq_consumer = None
            settings: RabbitSettings | None = (
                app_settings.RESOURCE_USAGE_TRACKER_RABBITMQ
            )
            if not settings:
                _logger.warning("RabbitMQ client is de-activated in the settings")
                return
            app.state.resource_tracker_rabbitmq_consumer = await _subscribe_to_rabbitmq(
                app
            )

    return _startup


def on_app_shutdown(app: FastAPI) -> Callable[[], Awaitable[None]]:
    async def _stop() -> None:
        if app.state.resource_tracker_rabbitmq_consumer:
            await _unsubscribe_from_rabbitmq(app)
            await app.state.rabbitmq_client.close()

    return _stop


def setup(app: FastAPI) -> None:
    app.add_event_handler("startup", on_app_startup(app))
    app.add_event_handler("shutdown", on_app_shutdown(app))
