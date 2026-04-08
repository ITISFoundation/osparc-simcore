import functools
import logging

from fastapi import FastAPI
from models_library.rabbitmq_messages import FileNotificationMessage
from servicelib.logging_utils import log_context
from servicelib.rabbitmq import RabbitMQClient

from ..core.rabbitmq import get_rabbitmq_client
from ..core.settings import ApplicationSettings
from ..services import container_extensions

_logger = logging.getLogger(__name__)


async def _handle_file_notification(app: FastAPI, data: bytes) -> bool:
    message = FileNotificationMessage.model_validate_json(data)
    _logger.debug("Received file notification: %s for file_id=%s", message.event_type, message.file_id)
    await container_extensions.notify_path_change(
        app=app, event_type=message.event_type, path=message.file_id, recursive=False
    )
    return True


def setup_file_notification_subscriber(app: FastAPI) -> None:
    async def _startup() -> None:
        settings: ApplicationSettings = app.state.settings
        topic = f"{settings.DY_SIDECAR_PROJECT_ID}.{settings.DY_SIDECAR_NODE_ID}"

        with log_context(_logger, logging.INFO, msg=f"subscribing to file notifications with topic={topic}"):
            rabbit_client: RabbitMQClient = get_rabbitmq_client(app)
            subscribed_queue, _ = await rabbit_client.subscribe(
                FileNotificationMessage.get_channel_name(),
                message_handler=functools.partial(_handle_file_notification, app),
                exclusive_queue=True,
                topics=[topic],
            )
            app.state.file_notification_queue = subscribed_queue

    async def _stop() -> None:
        queue_name: str = app.state.file_notification_queue
        with log_context(_logger, logging.INFO, msg=f"unsubscribing from file notifications with queue={queue_name}"):
            rabbit_client: RabbitMQClient = get_rabbitmq_client(app)
            await rabbit_client.unsubscribe(queue_name)

    app.add_event_handler("startup", _startup)
    app.add_event_handler("shutdown", _stop)
