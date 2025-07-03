from ..models.schemas import NotificationMessage, Recipient


async def send_notification(
    message: NotificationMessage, *recipients: list[Recipient]
) -> None: ...
