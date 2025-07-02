from fastapi import FastAPI
from servicelib.rabbitmq import RPCRouter

from ...models.schemas import NotificationMessage
from ...services import notifications_service

router = RPCRouter()


@router.expose(reraise_if_error_type=())
async def send_notification_message(
    app: FastAPI,
    *,
    message: NotificationMessage,
) -> None:
    await notifications_service.send_notification_message(message=message)
