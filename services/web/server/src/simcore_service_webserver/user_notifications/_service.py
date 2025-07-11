from typing import Any

from aiohttp import web
from models_library.users import UserID

from ._models import UserNotification, UserNotificationCreate
from ._repository import UserNotificationsRepository


async def list_user_notifications(
    app: web.Application, user_id: UserID, product_name: str
) -> list[UserNotification]:
    """List user notifications filtered by product"""
    repo = UserNotificationsRepository.create_from_app(app)
    return await repo.list_notifications(user_id=user_id, product_name=product_name)


async def create_user_notification(
    app: web.Application, notification_data: UserNotificationCreate
) -> None:
    """Create a new user notification"""
    repo = UserNotificationsRepository.create_from_app(app)
    user_notification = UserNotification.create_from_request_data(notification_data)
    await repo.create_notification(user_notification)


async def update_user_notification(
    app: web.Application,
    user_id: UserID,
    notification_id: str,
    update_data: dict[str, Any],
) -> bool:
    """Update a user notification. Returns True if found and updated."""
    repo = UserNotificationsRepository.create_from_app(app)
    return await repo.update_notification(
        user_id=user_id, notification_id=notification_id, update_data=update_data
    )
