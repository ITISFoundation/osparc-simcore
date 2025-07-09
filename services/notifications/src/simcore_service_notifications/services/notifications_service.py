import logging

from models_library.rpc.notifications.notifications import Notification
from servicelib.celery.models import TaskContext
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
        name=f"notifications.{notification.channel.type}",
        context=TaskContext(),  # TODO: TaskFilter
        queue=TaskQueue.DEFAULT,
        notification=notification,
    )
