# pylint: disable=redefined-outer-name

from typing import Any

import pytest
from models_library.users import UserID
from simcore_service_webserver.redis_user_notifications import (
    NotificationCategory,
    UserNotification,
    get_notification_key,
)


@pytest.mark.parametrize("raw_data", UserNotification.Config.schema_extra["examples"])
def test_user_notification(raw_data: dict[str.Any]) -> UserNotification:
    assert UserNotification.parse_obj(raw_data)


@pytest.mark.parametrize("user_id", [10])
async def test_get_notification_key(user_id: UserID):
    assert get_notification_key(user_id) == f"user_id={user_id}"


@pytest.mark.parametrize(
    "request_data",
    [
        {
            "user_id": "1",
            "category": NotificationCategory.NEW_ORGANIZATION,
            "actionable_path": "organization/40",
            "title": "New organization",
            "text": "You're now member of a new Organization",
            "date": "2023-02-23T16:23:13.122Z",
        }
    ],
)
async def test_user_notification_crate_from_request_data(request_data: dict[str, Any]):
    assert UserNotification.create_from_request_data(request_data)
