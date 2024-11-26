import functools
import logging
from collections.abc import Awaitable, Callable

from fastapi import FastAPI
from models_library.rabbitmq_messages import DynamicServiceRunningMessage
from servicelib.logging_utils import log_catch, log_context
from servicelib.rabbitmq import RabbitMQClient
from settings_library.rabbit import RabbitSettings

from ..core.settings import ApplicationSettings
from .modules.rabbitmq import get_rabbitmq_client
from .process_messages import process_dynamic_service_running_message

_logger = logging.getLogger(__name__)


_SEC = 1000  # in ms
_MIN = 60 * _SEC  # in ms
_HOUR = 60 * _MIN  # in ms

_EFS_MESSAGE_TTL_IN_MS = 2 * _HOUR


async def _subscribe_to_rabbitmq(app) -> str:
    with log_context(_logger, logging.INFO, msg="Subscribing to rabbitmq channel"):
        rabbit_client: RabbitMQClient = get_rabbitmq_client(app)
        subscribed_queue, _ = await rabbit_client.subscribe(
            DynamicServiceRunningMessage.get_channel_name(),
            message_handler=functools.partial(
                process_dynamic_service_running_message, app
            ),
            exclusive_queue=False,
            message_ttl=_EFS_MESSAGE_TTL_IN_MS,
        )
        return subscribed_queue


def _on_app_startup(app: FastAPI) -> Callable[[], Awaitable[None]]:
    async def _startup() -> None:
        with log_context(
            _logger, logging.INFO, msg="setup efs guardian process messages"
        ), log_catch(_logger, reraise=False):
            app_settings: ApplicationSettings = app.state.settings
            app.state.efs_guardian_rabbitmq_consumer = None
            settings: RabbitSettings | None = app_settings.EFS_GUARDIAN_RABBITMQ
            if not settings:
                _logger.warning("RabbitMQ client is de-activated in the settings")
                return
            app.state.efs_guardian_rabbitmq_consumer = await _subscribe_to_rabbitmq(app)

    return _startup


def _on_app_shutdown(
    _app: FastAPI,
) -> Callable[[], Awaitable[None]]:
    async def _stop() -> None:
        assert _app  # nosec

    return _stop


def setup(app: FastAPI) -> None:
    app.add_event_handler("startup", _on_app_startup(app))
    app.add_event_handler("shutdown", _on_app_shutdown(app))
