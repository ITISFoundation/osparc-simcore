import logging

from models_library.rpc.notifications import Notification
from servicelib.celery.models import TaskFilter
from servicelib.celery.task_manager import TaskManager

from ..modules.celery.tasks import TaskQueue

_logger = logging.getLogger(__name__)


async def send_notification(
    task_manager: TaskManager,
    *,
    notification: Notification,
) -> None:
    await task_manager.send_task(
        # send to the specific channel worker
        task_name=f"notifications.{notification.channel.type}",
        task_filter=TaskFilter(),  # TODO: TaskFilter
        task_queue=TaskQueue.DEFAULT,
        notification=notification,
    )
