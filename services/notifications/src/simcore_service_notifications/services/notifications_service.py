import logging

from models_library.rpc.notifications.messages import NotificationMessage, Recipient
from servicelib.celery.models import TaskContext
from servicelib.celery.task_manager import TaskManager

from ..modules.celery.tasks import TaskQueue

_logger = logging.getLogger(__name__)


async def send_notification_message(
    task_manager: TaskManager,
    *,
    message: NotificationMessage,
    recipients: list[Recipient],
) -> None:
    for recipient in recipients:
        await task_manager.send_task(
            name=f"notifications.{recipient.type}",
            context=TaskContext(),  # TODO: TaskFilter
            queue=TaskQueue.DEFAULT,
            message=message,
            recipient=recipient,
        )
