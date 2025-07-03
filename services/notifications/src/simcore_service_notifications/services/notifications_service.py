from servicelib.celery.task_manager import TaskManager

from ..models.schemas import NotificationMessage, Recipient


async def send_notification(
    task_manager: TaskManager,
    *,
    message: NotificationMessage,
    recipients: list[Recipient],
) -> None: ...
