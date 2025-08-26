from typing import Any

import redis.asyncio as aioredis
from aiohttp import web
from common_library.json_serialization import json_loads
from models_library.users import UserID
from servicelib.redis import handle_redis_returns_union_types

from ..redis import get_redis_user_notifications_client
from ._models import (
    MAX_NOTIFICATIONS_FOR_USER_TO_KEEP,
    MAX_NOTIFICATIONS_FOR_USER_TO_SHOW,
    UserNotification,
    get_notification_key,
)


class UserNotificationsRepository:
    def __init__(self, redis_client: aioredis.Redis) -> None:
        self._redis_client = redis_client

    @classmethod
    def create_from_app(cls, app: web.Application) -> "UserNotificationsRepository":
        return cls(redis_client=get_redis_user_notifications_client(app))

    async def list_notifications(
        self, user_id: UserID, product_name: str
    ) -> list[UserNotification]:
        """Returns a list of notifications where the latest notification is at index 0"""
        raw_notifications: list[str] = await handle_redis_returns_union_types(
            self._redis_client.lrange(
                get_notification_key(user_id),
                -1 * MAX_NOTIFICATIONS_FOR_USER_TO_SHOW,
                -1,
            )
        )
        notifications = [json_loads(x) for x in raw_notifications]

        # Make it backwards compatible
        for n in notifications:
            if "product" not in n:
                n["product"] = "UNDEFINED"

        # Filter by product
        included = [product_name, "UNDEFINED"]
        filtered_notifications = [n for n in notifications if n["product"] in included]
        return [UserNotification.model_validate(x) for x in filtered_notifications]

    async def create_notification(self, user_notification: UserNotification) -> None:
        """Insert at the head of the list and discard extra notifications"""
        key = get_notification_key(user_notification.user_id)
        async with self._redis_client.pipeline(transaction=True) as pipe:
            pipe.lpush(key, user_notification.model_dump_json())
            pipe.ltrim(key, 0, MAX_NOTIFICATIONS_FOR_USER_TO_KEEP - 1)
            await pipe.execute()

    async def update_notification(
        self, user_id: UserID, notification_id: str, update_data: dict[str, Any]
    ) -> bool:
        """Update a specific notification. Returns True if found and updated."""
        key = get_notification_key(user_id)
        all_user_notifications: list[UserNotification] = [
            UserNotification.model_validate_json(x)
            for x in await handle_redis_returns_union_types(
                self._redis_client.lrange(key, 0, -1)
            )
        ]

        for k, user_notification in enumerate(all_user_notifications):
            if notification_id == user_notification.id:
                # Update the notification with new data
                for field, value in update_data.items():
                    if hasattr(user_notification, field):
                        setattr(user_notification, field, value)

                await handle_redis_returns_union_types(
                    self._redis_client.lset(key, k, user_notification.model_dump_json())
                )
                return True
        return False
