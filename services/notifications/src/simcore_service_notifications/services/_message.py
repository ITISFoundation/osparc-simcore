import logging
from dataclasses import dataclass
from typing import Any

from models_library.celery import (
    GroupUUID,
    OwnerMetadata,
    TaskName,
    TaskUUID,
)
from servicelib.celery.async_jobs.notifications import (
    submit_send_message_task,
    submit_send_messages_task,
)
from servicelib.celery.task_manager import TaskManager

from .._meta import APP_NAME

_logger = logging.getLogger(__name__)

_OWNER_METADATA = OwnerMetadata(owner=APP_NAME)


def _fan_out_by_recipient(message: dict[str, Any]) -> list[dict[str, Any]]:
    """Splits a message with multiple recipients into one message per recipient."""
    recipients = message.get("to", [])
    if not isinstance(recipients, list) or len(recipients) <= 1:
        return [message]
    return [{**message, "to": recipient} for recipient in recipients]


@dataclass(frozen=True)
class MessagesService:
    task_manager: TaskManager

    async def send_message(
        self,
        *,
        message: dict[str, Any],
    ) -> tuple[TaskUUID | GroupUUID, TaskName]:
        per_recipient = _fan_out_by_recipient(message)

        if len(per_recipient) == 1:
            task_uuid, task_name = await submit_send_message_task(
                self.task_manager,
                owner_metadata=_OWNER_METADATA,
                message=per_recipient[0],
            )
            return task_uuid, task_name

        group_uuid, _, task_name = await submit_send_messages_task(
            self.task_manager,
            owner_metadata=_OWNER_METADATA,
            messages=per_recipient,
        )
        return group_uuid, task_name
