from datetime import datetime

from ..conversations import (
    ConversationID,
    ConversationMessageID,
    ConversationMessageType,
    ConversationType,
)
from ..groups import GroupID
from ..products import ProductName
from ..projects import ProjectID
from ..users import UserID
from ._base import InputSchema, OutputSchema


class ConversationRestGet(OutputSchema):
    conversation_id: ConversationID
    product_name: ProductName
    name: str
    project_uuid: ProjectID | None
    user_id: UserID
    type: ConversationType

    # states
    created: datetime
    modified: datetime


class ConversationMessageRestGet(OutputSchema):
    message_id: ConversationMessageID
    conversation_id: ConversationID
    user_group_id: GroupID
    content: str
    type: ConversationMessageType

    # states
    created: datetime
    modified: datetime


class ConversationPatch(InputSchema):
    name: str | None = None


class ConversationMessagePatch(InputSchema):
    content: str | None = None
