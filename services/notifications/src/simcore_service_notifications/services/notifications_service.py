from enum import StrEnum

from servicelib.celery.models import TaskContext, TaskMetadata
from servicelib.celery.task_manager import TaskManager

from ..models.schemas import NotificationMessage, Recipient


class TaskQueues(StrEnum):
    DEFAULT = "notifications.default"


async def send_notification(
    task_manager: TaskManager,
    *,
    message: NotificationMessage,
    recipients: list[Recipient],
) -> None:
    for recipient in recipients:
        await task_manager.send_task(
            TaskMetadata(
                name=f"notifications.{recipient.type}",
                queue=TaskQueues.DEFAULT,
            ),
            task_context=TaskContext(),
            message=message,
            recipient=recipient,
        )
