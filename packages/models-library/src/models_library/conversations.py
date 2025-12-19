from datetime import datetime
from enum import auto
from typing import Annotated, Any, TypeAlias
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints

from models_library.groups import GroupID
from models_library.projects import ProjectID

from .products import ProductName
from .utils.enums import StrAutoEnum

ConversationID: TypeAlias = UUID
ConversationName: TypeAlias = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
]

ConversationMessageID: TypeAlias = UUID


class ConversationType(StrAutoEnum):
    PROJECT_STATIC = auto()  # Static conversation for the project
    PROJECT_ANNOTATION = (
        auto()  # Something like sticky note, can be located anywhere in the pipeline UI
    )
    SUPPORT = auto()  # Support conversation
    SUPPORT_CALL = auto()  # Support call conversation

    def is_support_type(self) -> bool:
        return self in {ConversationType.SUPPORT, ConversationType.SUPPORT_CALL}

    def is_project_type(self) -> bool:
        return self in {
            ConversationType.PROJECT_STATIC,
            ConversationType.PROJECT_ANNOTATION,
        }


class ConversationMessageType(StrAutoEnum):
    MESSAGE = auto()
    NOTIFICATION = (
        auto()  # Special type of message used for storing notifications in the conversation
    )


#
# DB
#


class ConversationUserType(StrAutoEnum):
    SUPPORT_USER = auto()
    CHATBOT_USER = auto()
    REGULAR_USER = auto()


class ConversationGetDB(BaseModel):
    conversation_id: ConversationID
    product_name: ProductName
    name: ConversationName
    project_uuid: ProjectID | None
    user_group_id: GroupID
    type: ConversationType
    extra_context: dict[str, Any]
    fogbugz_case_id: str | None
    is_read_by_user: bool
    is_read_by_support: bool

    # states
    created: datetime
    modified: datetime
    last_message_created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                # Support message
                {
                    "conversation_id": "42838344-03de-4ce2-8d93-589a5dcdfd05",
                    "product_name": "osparc",
                    "name": "test_conversation",
                    "project_uuid": "42838344-03de-4ce2-8d93-589a5dcdfd05",
                    "user_group_id": "789",
                    "type": ConversationType.SUPPORT,
                    "extra_context": {},
                    "fogbugz_case_id": None,
                    "is_read_by_user": False,
                    "is_read_by_support": False,
                    "created": "2024-01-01T12:00:00",
                    "modified": "2024-01-01T12:00:00",
                    "last_message_created_at": "2024-01-01T12:00:00",
                }
            ]
        },
    )


class ConversationMessageGetDB(BaseModel):
    message_id: ConversationMessageID
    conversation_id: ConversationID
    user_group_id: GroupID
    content: str
    type: ConversationMessageType

    # states
    created: datetime
    modified: datetime

    model_config = ConfigDict(from_attributes=True)


class ConversationPatchDB(BaseModel):
    name: ConversationName | None = None
    extra_context: dict[str, Any] | None = None
    fogbugz_case_id: str | None = None
    is_read_by_user: bool | None = None
    is_read_by_support: bool | None = None
    last_message_created_at: datetime | None = None


class ConversationMessagePatchDB(BaseModel):
    content: str | None = None
