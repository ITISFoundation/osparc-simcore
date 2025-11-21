from datetime import datetime
from typing import Annotated, Any, Self

from pydantic import Field

from ..conversations import (
    ConversationGetDB,
    ConversationID,
    ConversationMessageGetDB,
    ConversationMessageID,
    ConversationMessageType,
    ConversationType,
)
from ..groups import GroupID
from ..products import ProductName
from ..projects import ProjectID
from ._base import InputSchema, OutputSchema

### CONVERSATION -------------------------------------------------------------------


class ConversationRestGet(OutputSchema):
    conversation_id: ConversationID
    product_name: ProductName
    name: Annotated[str, Field(max_length=50)]
    project_uuid: ProjectID | None
    user_group_id: GroupID
    type: ConversationType
    fogbugz_case_id: str | None
    created: datetime
    modified: datetime
    extra_context: dict[str, str]
    is_read_by_user: bool
    is_read_by_support: bool
    last_message_created_at: datetime

    @classmethod
    def from_domain_model(cls, domain: ConversationGetDB) -> Self:
        return cls(
            conversation_id=domain.conversation_id,
            product_name=domain.product_name,
            name=domain.name,
            project_uuid=domain.project_uuid,
            user_group_id=domain.user_group_id,
            type=domain.type,
            fogbugz_case_id=domain.fogbugz_case_id,
            created=domain.created,
            modified=domain.modified,
            extra_context=domain.extra_context,
            is_read_by_user=domain.is_read_by_user,
            is_read_by_support=domain.is_read_by_support,
            last_message_created_at=domain.last_message_created_at,
        )


class ConversationPatch(InputSchema):
    name: str | None = None
    extra_context: dict[str, Any] | None = None
    is_read_by_user: bool | None = None
    is_read_by_support: bool | None = None


### CONVERSATION MESSAGES ---------------------------------------------------------------


class ConversationMessageRestGet(OutputSchema):
    message_id: ConversationMessageID
    conversation_id: ConversationID
    user_group_id: GroupID
    content: Annotated[str, Field(max_length=4096)]
    type: ConversationMessageType
    created: datetime
    modified: datetime

    @classmethod
    def from_domain_model(cls, domain: ConversationMessageGetDB) -> Self:
        return cls(
            message_id=domain.message_id,
            conversation_id=domain.conversation_id,
            user_group_id=domain.user_group_id,
            content=domain.content,
            type=domain.type,
            created=domain.created,
            modified=domain.modified,
        )


class ConversationMessagePatch(InputSchema):
    content: str | None = None
