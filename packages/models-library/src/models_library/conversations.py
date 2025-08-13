from datetime import datetime
from enum import auto
from typing import Annotated, Any, TypeAlias
from uuid import UUID

from models_library.groups import GroupID
from models_library.projects import ProjectID
from pydantic import BaseModel, ConfigDict, StringConstraints

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


class ConversationMessageType(StrAutoEnum):
    MESSAGE = auto()
    NOTIFICATION = (
        auto()  # Special type of message used for storing notifications in the conversation
    )


#
# DB
#


class ConversationGetDB(BaseModel):
    conversation_id: ConversationID
    product_name: ProductName
    name: ConversationName
    project_uuid: ProjectID | None
    user_group_id: GroupID
    type: ConversationType
    extra_context: dict[str, Any]

    # states
    created: datetime
    modified: datetime

    model_config = ConfigDict(from_attributes=True)


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


class ConversationMessagePatchDB(BaseModel):
    content: str | None = None
