from enum import StrEnum

from models_library.rpc.notifications.messages import NotificationMessage, Recipient
from servicelib.celery.models import TaskContext
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
            name=f"notifications.{recipient.type}",
            context=TaskContext(),
            queue=TaskQueues.DEFAULT,
            message=message,
            recipient=recipient,
        )
