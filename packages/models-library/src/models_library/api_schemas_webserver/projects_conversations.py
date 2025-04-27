from datetime import datetime
from typing import Self

from ..conversations import (
    ConversationDB,
    ConversationID,
    ConversationMessageDB,
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

    @classmethod
    def from_domain_model(cls, domain: ConversationDB) -> Self:
        return cls(
            conversation_id=domain.conversation_id,
            product_name=domain.product_name,
            name=domain.name,
            project_uuid=domain.project_uuid,
            user_id=domain.user_id,
            type=domain.type,
            created=domain.created,
            modified=domain.modified,
        )


class ConversationMessageRestGet(OutputSchema):
    message_id: ConversationMessageID
    conversation_id: ConversationID
    user_group_id: GroupID
    content: str
    type: ConversationMessageType

    # states
    created: datetime
    modified: datetime

    @classmethod
    def from_domain_model(cls, domain: ConversationMessageDB) -> Self:
        return cls(
            message_id=domain.message_id,
            conversation_id=domain.conversation_id,
            user_group_id=domain.user_group_id,
            content=domain.content,
            type=domain.type,
            created=domain.created,
            modified=domain.modified,
        )


class ConversationPatch(InputSchema):
    name: str | None = None


class ConversationMessagePatch(InputSchema):
    content: str | None = None
