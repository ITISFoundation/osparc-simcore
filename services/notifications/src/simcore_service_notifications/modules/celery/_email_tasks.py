# pylint: disable=unused-argument

import logging

from celery import Task
from models_library.rpc.notifications.messages import EmailChannel, NotificationMessage
from servicelib.celery.models import TaskID

_logger = logging.getLogger(__name__)

EMAIL_CHANNEL_NAME = "email"


async def send_email(
    task: Task,
    task_id: TaskID,
    message: NotificationMessage,
) -> None:
    assert isinstance(message.channel, EmailChannel)  # nosec

    _logger.info("Sending email notification to %s", message.channel.to)
