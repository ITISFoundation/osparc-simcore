from ...models.schemas import EmailRecipient, NotificationMessage


async def send_email_notification(
    message: NotificationMessage, recipient: EmailRecipient
) -> None:
    pass
