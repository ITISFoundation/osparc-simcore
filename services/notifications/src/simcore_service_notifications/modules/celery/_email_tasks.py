# pylint: disable=unused-argument

import logging

from celery import Task  # type: ignore[import-untyped]
from models_library.rpc.notifications.messages import (
    EmailRecipient,
    NotificationMessage,
)
from servicelib.celery.models import TaskID

_logger = logging.getLogger(__name__)

EMAIL_CHANNEL_NAME = "email"


async def send_email(
    task: Task,
    task_id: TaskID,
    message: NotificationMessage,
    recipient: EmailRecipient,
) -> None:
    # TODO: render email template with message and recipient details
    #       and send the email using an email service
    _logger.info("Sending email notification to %s", recipient.address)
