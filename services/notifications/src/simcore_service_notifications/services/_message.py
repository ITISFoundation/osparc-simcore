import logging
from dataclasses import dataclass
from typing import Any

from models_library.celery import (
    GroupUUID,
    OwnerMetadata,
    TaskName,
    TaskUUID,
)
from models_library.notifications.errors import (
    NotificationsTooManyRecipientsError,
)
from models_library.notifications.rpc import Addressing, EmailMessage, Message
from servicelib.celery.async_jobs.notifications import (
    submit_send_message_task,
    submit_send_messages_task,
)
from servicelib.celery.task_manager import TaskManager

from .._meta import APP_NAME
from ..core.settings import ApplicationSettings
from ..models.template import TemplateRef
from ._template import TemplateService
from .channel_handlers import for_channel

_logger = logging.getLogger(__name__)

_OWNER_METADATA = OwnerMetadata(owner=APP_NAME)


def _prepare_celery_messages(message: Message) -> list[dict[str, Any]]:
    """Dispatches to channel handler to fan out into per-recipient celery payloads.

    Raises:
        NotificationsUnsupportedChannelError: If the channel is not supported.
    """
    handler = for_channel(message.channel)
    return handler.prepare_messages(message)


@dataclass(frozen=True)
class MessageService:
    template_service: TemplateService
    task_manager: TaskManager
    settings: ApplicationSettings

    async def send_message(
        self,
        *,
        message: Message,
        owner_metadata: OwnerMetadata | None = None,
    ) -> tuple[TaskUUID | GroupUUID, TaskName]:
        resolved_owner = owner_metadata or _OWNER_METADATA
        messages = _prepare_celery_messages(message)

        num_recipients = len(messages)
        if num_recipients == 1:
            task_uuid, task_name = await submit_send_message_task(
                self.task_manager,
                owner_metadata=resolved_owner,
                message=messages[0],
            )
            return task_uuid, task_name

        max_recipients = self.settings.NOTIFICATIONS_EMAIL_MAX_RECIPIENTS_PER_MESSAGE
        if num_recipients > max_recipients:
            raise NotificationsTooManyRecipientsError(
                num_recipients=num_recipients,
                max_recipients=max_recipients,
            )

        group_uuid, _, task_name = await submit_send_messages_task(
            self.task_manager,
            owner_metadata=resolved_owner,
            messages=messages,
        )
        return group_uuid, task_name

    async def send_message_from_template(
        self,
        *,
        addressing: Addressing,
        ref: TemplateRef,
        context: dict[str, Any],
        owner_metadata: OwnerMetadata | None = None,
    ) -> tuple[TaskUUID | GroupUUID, TaskName]:
        preview = self.template_service.preview_template(ref=ref, context=context)
        message = EmailMessage(
            addressing=addressing,
            content=preview.message_content.model_dump(),
        )
        return await self.send_message(
            message=message,
            owner_metadata=owner_metadata,
        )
