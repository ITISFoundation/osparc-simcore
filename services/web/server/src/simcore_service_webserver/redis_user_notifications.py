from copy import deepcopy
from datetime import datetime
from enum import auto
from typing import Any, Final
from uuid import uuid4

from models_library.users import UserID
from models_library.utils.enums import StrAutoEnum
from pydantic import BaseModel, NonNegativeInt, validator

MAX_NOTIFICATIONS_FOR_USER: Final[NonNegativeInt] = 10


def get_notification_key(user_id: UserID) -> str:
    return f"user_id={user_id}"


class NotificationCategory(StrAutoEnum):
    NEW_ORGANIZATION = auto()
    STUDY_SHARED = auto()
    TEMPLATE_SHARED = auto()


class UserNotification(BaseModel):
    id: str
    user_id: UserID
    category: NotificationCategory
    actionable_path: str
    title: str
    text: str
    date: datetime
    read: bool

    def update_from(self, data: dict[str, Any]) -> None:
        for k, v in data.items():
            self.__setattr__(k, v)

    @validator("category", pre=True)
    @classmethod
    def category_to_upper(cls, value: str) -> str:
        return value.upper()

    @classmethod
    def create_from_request_data(
        cls, request_data: dict[str, Any]
    ) -> "UserNotification":
        params = deepcopy(request_data)
        params["id"] = f"{uuid4()}"
        params["read"] = False
        return cls.parse_obj(params)

    class Config:
        schema_extra = {
            "examples": [
                {
                    "id": "123",
                    "user_id": "1",
                    "category": "new_organization",
                    "actionable_path": "organization/40",
                    "title": "New organization",
                    "text": "You're now member of a new Organization",
                    "date": "2023-02-23T16:23:13.122Z",
                    "read": True,
                },
                {
                    "id": "456",
                    "user_id": "1",
                    "category": "STUDY_SHARED",
                    "actionable_path": "study/27edd65c-b360-11ed-93d7-02420a000014",
                    "title": "Study shared",
                    "text": "A study was shared with you",
                    "date": "2023-02-23T16:25:13.122Z",
                    "read": False,
                },
                {
                    "id": "789",
                    "user_id": "1",
                    "category": "TEMPLATE_SHARED",
                    "actionable_path": "template/f60477b6-a07e-11ed-8d29-02420a00002d",
                    "title": "Template shared",
                    "text": "A template was shared with you",
                    "date": "2023-02-23T16:28:13.122Z",
                    "read": False,
                },
            ]
        }
