import logging
from dataclasses import dataclass
from typing import Any

from models_library.celery import (
    GroupUUID,
    OwnerMetadata,
    TaskName,
    TaskUUID,
)
from models_library.notifications import ChannelType
from models_library.notifications.errors import NotificationsUnsupportedChannelError
from pydantic import TypeAdapter
from servicelib.celery.async_jobs.notifications import (
    submit_send_message_task,
    submit_send_messages_task,
)
from servicelib.celery.task_manager import TaskManager

from .._meta import APP_NAME
from ..models.template import TemplateRef
from ._template import TemplateService
from .channel_handlers import for_channel

_logger = logging.getLogger(__name__)

_OWNER_METADATA = OwnerMetadata(owner=APP_NAME)


def _validate_and_prepare_messages(message: dict[str, Any]) -> list[dict[str, Any]]:
    """Validates incoming message and returns channel-specific celery payloads.

    Raises:
        NotificationsUnsupportedChannelError: If the channel is not supported.
        pydantic.ValidationError: If the message does not conform to the channel model.
    """
    raw_channel = message.get("channel")

    try:
        channel = TypeAdapter(ChannelType).validate_python(raw_channel)
    except ValueError as exc:
        raise NotificationsUnsupportedChannelError(channel=raw_channel) from exc

    handler = for_channel(channel)
    return handler.prepare_messages(message)


@dataclass(frozen=True)
class MessageService:
    template_service: TemplateService
    task_manager: TaskManager

    async def send_message(
        self,
        *,
        message: dict[str, Any],
        owner_metadata: OwnerMetadata | None = None,
    ) -> tuple[TaskUUID | GroupUUID, TaskName]:
        resolved_owner = owner_metadata or _OWNER_METADATA
        messages = _validate_and_prepare_messages(message)

        if len(messages) == 1:
            task_uuid, task_name = await submit_send_message_task(
                self.task_manager,
                owner_metadata=resolved_owner,
                message=messages[0],
            )
            return task_uuid, task_name

        group_uuid, _, task_name = await submit_send_messages_task(
            self.task_manager,
            owner_metadata=resolved_owner,
            messages=messages,
        )
        return group_uuid, task_name

    async def send_message_from_template(
        self,
        *,
        envelope: dict[str, Any],
        ref: TemplateRef,
        context: dict[str, Any],
        owner_metadata: OwnerMetadata | None = None,
    ) -> tuple[TaskUUID | GroupUUID, TaskName]:
        preview = self.template_service.preview_template(ref=ref, context=context)
        message = {
            "channel": ref.channel,
            **envelope,
            "content": preview.message_content.model_dump(),
        }
        return await self.send_message(
            message=message,
            owner_metadata=owner_metadata,
        )
