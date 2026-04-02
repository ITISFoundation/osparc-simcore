import logging
from typing import cast

from fastapi import FastAPI
from models_library.basic_regex import SIMCORE_S3_FILE_ID_ALLOWED_PREFIXES
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID, StorageFileID
from models_library.rabbitmq_messages import (
    FileNotificationEventType,
    FileNotificationMessage,
)
from models_library.users import UserID
from servicelib.logging_utils import log_catch, log_context
from servicelib.rabbitmq import RabbitMQClient

from .._meta import APP_NAME
from ..core.settings import get_application_settings

_logger = logging.getLogger(__name__)


def setup_rabbitmq(app: FastAPI) -> None:
    async def on_startup() -> None:
        settings = get_application_settings(app).STORAGE_RABBITMQ
        app.state.rabbitmq_client = RabbitMQClient(
            client_name=f"{APP_NAME}",
            settings=settings,
        )

    async def on_shutdown() -> None:
        if app.state.rabbitmq_client:
            await cast(RabbitMQClient, app.state.rabbitmq_client).close()
            app.state.rabbitmq_client = None

    app.state.rabbitmq_client = None
    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)


def get_rabbitmq_client(app: FastAPI) -> RabbitMQClient:
    return cast(RabbitMQClient, app.state.rabbitmq_client)


async def post_file_notification(
    app: FastAPI,
    *,
    event_type: FileNotificationEventType,
    user_id: UserID,
    file_id: StorageFileID,
) -> None:
    with (
        log_catch(_logger, reraise=False),
        log_context(_logger, logging.DEBUG, msg=f"Posting file notification for {file_id=} with {event_type=}"),
    ):
        parts = f"{file_id}".split("/")

        if parts[0] in SIMCORE_S3_FILE_ID_ALLOWED_PREFIXES:
            _logger.debug("Skip notification for file_id=%s starting with prefix %s", file_id, parts[0])
            return

        project_id = ProjectID(parts[0]) if len(parts) > 0 else None
        node_id = NodeID(parts[1]) if len(parts) > 1 else None

        if project_id is None or node_id is None:
            _logger.warning(
                "Skip notification for file_id=%s because project and node ids could not be extracted", file_id
            )
            return

        message = FileNotificationMessage(
            event_type=event_type,
            user_id=user_id,
            project_id=project_id,
            node_id=node_id,
            file_id=file_id,
        )
        await get_rabbitmq_client(app).publish(message.channel_name, message)
