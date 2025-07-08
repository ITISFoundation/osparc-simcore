from models_library.rpc.notifications.messages import NotificationMessage
from servicelib.celery.task_manager import TaskManager
from servicelib.rabbitmq import RPCRouter

from ...services import notifications_service

router = RPCRouter()


@router.expose(reraise_if_error_type=())
async def send_notification_message(
    task_manager: TaskManager,
    *,
    message: NotificationMessage,
) -> None:
    await notifications_service.send_notification_message(
        task_manager,
        message=message,
    )
