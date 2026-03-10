import logging
from dataclasses import dataclass
from typing import Any

from servicelib.celery.async_jobs.notifications import (
    NOTIFICATIONS_SERVICE_QUEUE_NAME,
    SEND_MESSAGE_TASK_NAME_TEMPLATE,
)
from servicelib.celery.models import ExecutionMetadata, GroupUUID, OwnerMetadata, TaskName, TaskUUID
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
        task_name = SEND_MESSAGE_TASK_NAME_TEMPLATE.format(message["channel"])

        if len(per_recipient) == 1:
            task_uuid = await self.task_manager.submit_task(
                ExecutionMetadata(
                    name=task_name,
                    queue=NOTIFICATIONS_SERVICE_QUEUE_NAME,
                ),
                owner_metadata=_OWNER_METADATA,
                message=per_recipient[0],
            )
            return task_uuid, task_name

        group_uuid, _ = await self.task_manager.submit_group(
            [
                (
                    ExecutionMetadata(
                        name=task_name,
                        queue=NOTIFICATIONS_SERVICE_QUEUE_NAME,
                    ),
                    {"message": msg},
                )
                for msg in per_recipient
            ],
            owner_metadata=_OWNER_METADATA,
        )
        return group_uuid, task_name
