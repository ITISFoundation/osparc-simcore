# pylint: disable=redefined-outer-name

from typing import Any

import pytest
from models_library.users import UserID
from simcore_service_webserver.users._notifications import (
    NotificationCategory,
    UserNotification,
    UserNotificationCreate,
    get_notification_key,
)


@pytest.mark.parametrize(
    "raw_data", UserNotification.model_config["json_schema_extra"]["examples"]
)
def test_user_notification(raw_data: dict[str, Any]):
    assert UserNotification.model_validate(raw_data)


@pytest.mark.parametrize("user_id", [10])
def test_get_notification_key(user_id: UserID):
    assert get_notification_key(user_id) == f"user_id={user_id}"


@pytest.mark.parametrize(
    "request_data",
    [
        pytest.param(
            UserNotificationCreate.model_validate(
                {
                    "user_id": "1",
                    "category": NotificationCategory.NEW_ORGANIZATION,
                    "actionable_path": "organization/40",
                    "title": "New organization",
                    "text": "You're now member of a new Organization",
                    "date": "2023-02-23T16:23:13.122Z",
                    "product": "osparc",
                }
            ),
            id="normal_usage",
        ),
        pytest.param(
            UserNotificationCreate.model_validate(
                {
                    "user_id": "1",
                    "category": NotificationCategory.NEW_ORGANIZATION,
                    "actionable_path": "organization/40",
                    "title": "New organization",
                    "text": "You're now member of a new Organization",
                    "date": "2023-02-23T16:23:13.122Z",
                    "product": "osparc",
                    "read": True,
                }
            ),
            id="read_is_always_set_false",
        ),
        pytest.param(
            UserNotificationCreate.model_validate(
                {
                    "id": "some_id",
                    "user_id": "1",
                    "category": NotificationCategory.NEW_ORGANIZATION,
                    "actionable_path": "organization/40",
                    "title": "New organization",
                    "text": "You're now member of a new Organization",
                    "date": "2023-02-23T16:23:13.122Z",
                    "product": "osparc",
                }
            ),
            id="a_new_id_is_alway_recreated",
        ),
        pytest.param(
            UserNotificationCreate.model_validate(
                {
                    "id": "some_id",
                    "user_id": "1",
                    "category": "NEW_ORGANIZATION",
                    "actionable_path": "organization/40",
                    "title": "New organization",
                    "text": "You're now member of a new Organization",
                    "date": "2023-02-23T16:23:13.122Z",
                    "product": "s4l",
                    "resource_id": "other_id",
                    "user_from_id": "2",
                }
            ),
            id="category_from_string",
        ),
        pytest.param(
            UserNotificationCreate.model_validate(
                {
                    "id": "some_id",
                    "user_id": "1",
                    "category": "NEW_ORGANIZATION",
                    "actionable_path": "organization/40",
                    "title": "New organization",
                    "text": "You're now member of a new Organization",
                    "date": "2023-02-23T16:23:13.122Z",
                    "product": "tis",
                    "resource_id": "other_id",
                    "user_from_id": "2",
                }
            ),
            id="category_from_lower_case_string",
        ),
    ],
)
def test_user_notification_create_from_request_data(
    request_data: UserNotificationCreate,
):
    user_notification = UserNotification.create_from_request_data(request_data)
    assert user_notification.id
    assert user_notification.read is False
