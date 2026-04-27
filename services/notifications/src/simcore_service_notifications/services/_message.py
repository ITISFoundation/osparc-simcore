import logging
from dataclasses import dataclass
from typing import Any

from models_library.celery import (
    TaskID,
    TaskName,
)
from models_library.notifications import Channel
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


def _prepare_celery_messages(message: Message) -> list[dict[str, Any]]:
    """Dispatches to channel handler to fan out into per-recipient celery payloads.

    Raises:
        NotificationsUnsupportedChannelError: If the channel is not supported.
    """
    handler = for_channel(message.channel)
    return handler.prepare_messages(message)


def _get_task_description(message: Message) -> str | None:
    if message.channel == Channel.email:
        if isinstance(message, EmailMessage):
            return message.content.subject
        return None
    return None


@dataclass(frozen=True)
class MessageService:
    template_service: TemplateService
    task_manager: TaskManager
    settings: ApplicationSettings

    async def send_message(
        self,
        *,
        message: Message,
        owner: str | None = None,
        user_id: int | None = None,
        product_name: str | None = None,
    ) -> tuple[TaskID, TaskName]:
        resolved_owner = owner or APP_NAME
        messages = _prepare_celery_messages(message)

        num_recipients = len(messages)
        description = _get_task_description(message)

        if num_recipients == 1:
            task_id, task_name = await submit_send_message_task(
                self.task_manager,
                owner=resolved_owner,
                user_id=user_id,
                product_name=product_name,
                message=messages[0],
                description=description,
            )
            return task_id, task_name

        max_recipients = self.settings.NOTIFICATIONS_EMAIL_MAX_RECIPIENTS_PER_MESSAGE
        if num_recipients > max_recipients:
            raise NotificationsTooManyRecipientsError(
                num_recipients=num_recipients,
                max_recipients=max_recipients,
            )

        group_id, _, task_name = await submit_send_messages_task(
            self.task_manager,
            owner=resolved_owner,
            user_id=user_id,
            product_name=product_name,
            messages=messages,
            description=description,
        )
        return group_id, task_name

    async def send_message_from_template(
        self,
        *,
        addressing: Addressing,
        ref: TemplateRef,
        context: dict[str, Any],
        owner: str | None = None,
        user_id: int | None = None,
        product_name: str | None = None,
    ) -> tuple[TaskID, TaskName]:
        preview = self.template_service.preview_template(ref=ref, context=context)
        message = EmailMessage(
            addressing=addressing,
            content=preview.message_content.model_dump(),
        )
        return await self.send_message(
            message=message,
            owner=owner,
            user_id=user_id,
            product_name=product_name,
        )
