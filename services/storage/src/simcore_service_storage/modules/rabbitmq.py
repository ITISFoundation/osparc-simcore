import logging

from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager
from models_library.basic_regex import SIMCORE_S3_FILE_ID_ALLOWED_PREFIXES
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID, StorageFileID
from models_library.rabbitmq_messages import (
    FileNotificationEventType,
    FileNotificationMessage,
)
from models_library.users import UserID
from servicelib.fastapi.rabbitmq_lifespan import configure_rabbitmq_client as _configure_rabbitmq_client
from servicelib.logging_utils import log_catch, log_context
from servicelib.rabbitmq import RabbitMQClient
from settings_library.rabbit import RabbitSettings

from .._meta import APP_NAME

_logger = logging.getLogger(__name__)


def configure_rabbitmq_client(
    app_lifespan: LifespanManager,
    *,
    settings: RabbitSettings,
) -> None:
    """Configure RabbitMQ client lifespan."""
    _configure_rabbitmq_client(
        app_lifespan,
        settings=settings,
        client_name=APP_NAME,
        wait_for_connectivity=False,
    )


def get_rabbitmq_client(app: FastAPI) -> RabbitMQClient:
    rabbit_client: RabbitMQClient = app.state.rabbitmq_client
    return rabbit_client


async def post_file_notification(
    app: FastAPI,
    *,
    event_type: FileNotificationEventType,
    user_id: UserID,
    file_id: StorageFileID,
    fmd_is_directory: bool,
) -> None:
    with (
        log_catch(_logger, reraise=False),
        log_context(_logger, logging.DEBUG, msg=f"posting file notification for {file_id=} with {event_type=}"),
    ):
        parts = f"{file_id}".split("/")

        if parts[0] in SIMCORE_S3_FILE_ID_ALLOWED_PREFIXES:
            _logger.info("Skip notification for file_id=%s starting with prefix %s", file_id, parts[0])
            return

        try:
            project_id = ProjectID(parts[0]) if len(parts) > 0 else None
        except ValueError:
            project_id = None
        try:
            node_id = NodeID(parts[1]) if len(parts) > 1 else None
        except ValueError:
            node_id = None

        if project_id is None or node_id is None:
            _logger.warning(
                "Skip notification for file_id=%s because project_id=%s or node_id=%s could not be extracted",
                file_id,
                project_id,
                node_id,
            )
            return

        message = FileNotificationMessage(
            event_type=event_type,
            user_id=user_id,
            project_id=project_id,
            node_id=node_id,
            file_id=file_id,
            fmd_is_directory=fmd_is_directory,
        )
        await get_rabbitmq_client(app).publish(message.channel_name, message)
