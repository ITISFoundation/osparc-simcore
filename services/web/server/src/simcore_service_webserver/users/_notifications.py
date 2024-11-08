from datetime import datetime
from enum import auto
from typing import Final, Literal
from uuid import uuid4

from models_library.products import ProductName
from models_library.users import UserID
from models_library.utils.enums import StrAutoEnum
from pydantic import BaseModel, ConfigDict, NonNegativeInt, field_validator

MAX_NOTIFICATIONS_FOR_USER_TO_SHOW: Final[NonNegativeInt] = 10
MAX_NOTIFICATIONS_FOR_USER_TO_KEEP: Final[NonNegativeInt] = 100


def get_notification_key(user_id: UserID) -> str:
    return f"user_id={user_id}"


class NotificationCategory(StrAutoEnum):
    NEW_ORGANIZATION = auto()
    STUDY_SHARED = auto()
    TEMPLATE_SHARED = auto()
    ANNOTATION_NOTE = auto()
    WALLET_SHARED = auto()


class BaseUserNotification(BaseModel):
    user_id: UserID
    category: NotificationCategory
    actionable_path: str
    title: str
    text: str
    date: datetime
    product: Literal["UNDEFINED"] | ProductName = "UNDEFINED"
    resource_id: Literal[""] | str = ""
    user_from_id: Literal[None] | UserID = None

    @field_validator("category", mode="before")
    @classmethod
    def category_to_upper(cls, value: str) -> str:
        return value.upper()


class UserNotificationCreate(BaseUserNotification):
    ...


class UserNotificationPatch(BaseModel):
    read: bool


class UserNotification(BaseUserNotification):
    # Ideally the `id` field, will be a UUID type in the future.
    # Since there is no Redis data migration service, data type
    # will not change to UUID nor Union[str, UUID]
    id: str
    read: bool

    @classmethod
    def create_from_request_data(
        cls, request_data: UserNotificationCreate
    ) -> "UserNotification":
        return cls.model_construct(
            id=f"{uuid4()}", read=False, **request_data.model_dump()
        )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "id": "3fb96d89-ff5d-4d27-b5aa-d20d46e20eb8",
                    "user_id": "1",
                    "category": "NEW_ORGANIZATION",
                    "actionable_path": "organization/40",
                    "title": "New organization",
                    "text": "You're now member of a new Organization",
                    "date": "2023-02-23T16:23:13.122Z",
                    "product": "osparc",
                    "read": True,
                },
                {
                    "id": "ba64ffce-c58c-4382-aad6-96a7787251d6",
                    "user_id": "1",
                    "category": "STUDY_SHARED",
                    "actionable_path": "study/27edd65c-b360-11ed-93d7-02420a000014",
                    "title": "Study shared",
                    "text": "A study was shared with you",
                    "date": "2023-02-23T16:25:13.122Z",
                    "product": "osparc",
                    "read": False,
                },
                {
                    "id": "390053c9-3931-40e1-839f-585268f6fd3c",
                    "user_id": "1",
                    "category": "TEMPLATE_SHARED",
                    "actionable_path": "template/f60477b6-a07e-11ed-8d29-02420a00002d",
                    "title": "Template shared",
                    "text": "A template was shared with you",
                    "date": "2023-02-23T16:28:13.122Z",
                    "product": "osparc",
                    "read": False,
                },
                {
                    "id": "390053c9-3931-40e1-839f-585268f6fd3d",
                    "user_id": "1",
                    "category": "ANNOTATION_NOTE",
                    "actionable_path": "study/27edd65c-b360-11ed-93d7-02420a000014",
                    "title": "Note added",
                    "text": "A Note was added for you",
                    "date": "2023-02-23T16:28:13.122Z",
                    "product": "s4l",
                    "read": False,
                    "resource_id": "3fb96d89-ff5d-4d27-b5aa-d20d46e20e12",
                    "user_from_id": "2",
                },
                {
                    "id": "390053c9-3931-40e1-839f-585268f6fd3e",
                    "user_id": "1",
                    "category": "WALLET_SHARED",
                    "actionable_path": "wallet/21",
                    "title": "Credits shared",
                    "text": "A Credit account was shared with you",
                    "date": "2023-09-29T16:28:13.122Z",
                    "product": "tis",
                    "read": False,
                    "resource_id": "3fb96d89-ff5d-4d27-b5aa-d20d46e20e13",
                    "user_from_id": "2",
                },
            ]
        }
    )
