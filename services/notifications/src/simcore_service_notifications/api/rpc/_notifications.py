from servicelib.celery.task_manager import TaskManager
from servicelib.rabbitmq import RPCRouter

from ...models.schemas import NotificationMessage, Recipient
from ...services import notifications_service

router = RPCRouter()


@router.expose(reraise_if_error_type=())
async def send_notification_message(
    task_manager: TaskManager,
    *,
    message: NotificationMessage,
    recipients: list[Recipient],
) -> None:
    await notifications_service.send_notification(
        task_manager, message=message, recipients=recipients
    )
