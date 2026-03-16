import logging
from dataclasses import dataclass
from typing import Any

from models_library.celery import (
    GroupUUID,
    OwnerMetadata,
    TaskName,
    TaskUUID,
)
from models_library.notifications import ChannelType, EmailMessage
from models_library.notifications.celery import EmailMessage as CeleryEmailMessage
from models_library.notifications.errors import NotificationsUnsupportedChannelError
from servicelib.celery.async_jobs.notifications import (
    submit_send_message_task,
    submit_send_messages_task,
)
from servicelib.celery.task_manager import TaskManager

from .._meta import APP_NAME
from ..models.template import TemplateRef
from ._template import TemplateService

_logger = logging.getLogger(__name__)

_OWNER_METADATA = OwnerMetadata(owner=APP_NAME)


def _validate_and_fan_out_email(message: dict[str, Any]) -> list[dict[str, Any]]:
    """Validates an incoming email message and fans out into per-recipient celery payloads."""
    email_msg = EmailMessage.model_validate(message)
    content_dict = email_msg.content.model_dump()
    from_dict = email_msg.from_.model_dump()

    return [
        CeleryEmailMessage.model_validate(
            {
                "channel": email_msg.channel,
                "from": from_dict,
                "to": recipient.model_dump(),
                "content": content_dict,
            }
        ).model_dump(by_alias=True)
        for recipient in email_msg.to
    ]


def _validate_and_prepare_messages(message: dict[str, Any]) -> list[dict[str, Any]]:
    """Validates incoming message and returns channel-specific celery payloads.

    Raises:
        NotificationsUnsupportedChannelError: If the channel is not supported.
        pydantic.ValidationError: If the message does not conform to the channel model.
    """
    channel = message.get("channel")
    match channel:
        case ChannelType.email:
            return _validate_and_fan_out_email(message)
        case _:
            raise NotificationsUnsupportedChannelError(channel=channel)


@dataclass(frozen=True)
class MessageService:
    task_manager: TaskManager
    template_service: TemplateService

    async def send_message(
        self,
        *,
        message: dict[str, Any],
    ) -> tuple[TaskUUID | GroupUUID, TaskName]:
        celery_messages = _validate_and_prepare_messages(message)

        if len(celery_messages) == 1:
            task_uuid, task_name = await submit_send_message_task(
                self.task_manager,
                owner_metadata=_OWNER_METADATA,
                message=celery_messages[0],
            )
            return task_uuid, task_name

        group_uuid, _, task_name = await submit_send_messages_task(
            self.task_manager,
            owner_metadata=_OWNER_METADATA,
            messages=celery_messages,
        )
        return group_uuid, task_name

    async def send_message_from_template(
        self,
        *,
        envelope: dict[str, Any],
        ref: TemplateRef,
        context: dict[str, Any],
    ) -> tuple[TaskUUID | GroupUUID, TaskName]:
        preview = self.template_service.preview_template(ref=ref, context=context)
        message = {
            "channel": ref.channel,
            **envelope,
            "content": preview.message_content.model_dump()
            if hasattr(preview.message_content, "model_dump")
            else preview.message_content,
        }
        return await self.send_message(message=message)
