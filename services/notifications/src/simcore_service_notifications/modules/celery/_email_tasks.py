import logging

from celery import Task  # type: ignore[import-untyped]

from ...models.schemas import EmailRecipient, NotificationMessage

_logger = logging.getLogger(__name__)


async def send_email(
    task: Task,
    message: NotificationMessage,
    recipient: EmailRecipient,
) -> None:
    # TODO: render email template with message and recipient details
    #       and send the email using an email service
    _logger.info(f"Sending email notification to {recipient.address}")
