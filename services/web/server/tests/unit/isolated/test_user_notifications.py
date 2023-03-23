# pylint: disable=redefined-outer-name

from typing import Any

import pytest
from models_library.users import UserID
from simcore_service_webserver.user_notifications import (
    NotificationCategory,
    UserNotification,
    get_notification_key,
)


@pytest.mark.parametrize("raw_data", UserNotification.Config.schema_extra["examples"])
def test_user_notification(raw_data: dict[str, Any]) -> UserNotification:
    assert UserNotification.parse_obj(raw_data)


@pytest.mark.parametrize("user_id", [10])
def test_get_notification_key(user_id: UserID):
    assert get_notification_key(user_id) == f"user_id={user_id}"


@pytest.mark.parametrize(
    "request_data",
    [
        pytest.param(
            {
                "user_id": "1",
                "category": NotificationCategory.NEW_ORGANIZATION,
                "actionable_path": "organization/40",
                "title": "New organization",
                "text": "You're now member of a new Organization",
                "date": "2023-02-23T16:23:13.122Z",
            },
            id="normal_usage",
        ),
        pytest.param(
            {
                "user_id": "1",
                "category": NotificationCategory.NEW_ORGANIZATION,
                "actionable_path": "organization/40",
                "title": "New organization",
                "text": "You're now member of a new Organization",
                "date": "2023-02-23T16:23:13.122Z",
                "read": True,
            },
            id="read_is_always_set_false",
        ),
        pytest.param(
            {
                "user_id": "1",
                "category": NotificationCategory.NEW_ORGANIZATION,
                "actionable_path": "organization/40",
                "title": "New organization",
                "text": "You're now member of a new Organization",
                "date": "2023-02-23T16:23:13.122Z",
                "id": "some_id",
            },
            id="a_new_id_is_alway_recreated",
        ),
        pytest.param(
            {
                "user_id": "1",
                "category": "NEW_ORGANIZATION",
                "actionable_path": "organization/40",
                "title": "New organization",
                "text": "You're now member of a new Organization",
                "date": "2023-02-23T16:23:13.122Z",
                "id": "some_id",
            },
            id="category_from_string",
        ),
        pytest.param(
            {
                "user_id": "1",
                "category": "NEW_ORGANIZATION",
                "actionable_path": "organization/40",
                "title": "New organization",
                "text": "You're now member of a new Organization",
                "date": "2023-02-23T16:23:13.122Z",
                "id": "some_id",
            },
            id="category_from_lower_case_string",
        ),
    ],
)
def test_user_notification_crate_from_request_data(request_data: dict[str, Any]):
    user_notification = UserNotification.create_from_request_data(request_data)
    assert user_notification.id != request_data.get("id", None)
    assert user_notification.read is False


def test_user_notification_update_from():
    user_notification = UserNotification.create_from_request_data(
        UserNotification.Config.schema_extra["examples"][0]
    )
    assert user_notification.read is False
    user_notification.update_from({"read": True})
    assert user_notification.read is True
