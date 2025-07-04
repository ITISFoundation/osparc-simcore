from enum import StrEnum

from models_library.rpc.notifications.messages import NotificationMessage, Recipient
from servicelib.celery.models import TaskContext, TaskMetadata
from servicelib.celery.task_manager import TaskManager


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
