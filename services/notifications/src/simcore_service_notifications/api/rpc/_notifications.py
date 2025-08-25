from models_library.rpc.notifications import Notification
from servicelib.celery.task_manager import TaskManager
from servicelib.rabbitmq import RPCRouter

from ...services import notifications_service

router = RPCRouter()


@router.expose(reraise_if_error_type=())
async def send_notification(
    task_manager: TaskManager,
    *,
    notification: Notification,
) -> None:
    await notifications_service.send_notification(
        task_manager,
        notification=notification,
    )
