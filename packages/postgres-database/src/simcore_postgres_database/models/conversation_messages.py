import enum

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from ._common import RefActions, column_created_datetime, column_modified_datetime
from .base import metadata
from .conversations import conversations
from .groups import groups


class ConversationMessageType(enum.Enum):
    MESSAGE = "MESSAGE"
    NOTIFICATION = "NOTIFICATION"  # Special type of message used for storing notifications in the conversation


conversation_messages = sa.Table(
    "conversation_messages",
    metadata,
    sa.Column(
        "message_id",
        UUID(as_uuid=True),
        nullable=False,
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    ),
    sa.Column(
        "conversation_id",
        UUID(as_uuid=True),
        sa.ForeignKey(
            conversations.c.conversation_id,
            name="fk_conversation_messages_project_uuid",
            ondelete=RefActions.CASCADE,
            onupdate=RefActions.CASCADE,
        ),
        index=True,
        nullable=False,
    ),
    # NOTE: if the user primary group ID gets deleted, it sets to null which should be interpreted as "unknown" user
    sa.Column(
        "user_group_id",
        sa.BigInteger,
        sa.ForeignKey(
            groups.c.gid,
            name="fk_conversation_messages_user_primary_gid",
            ondelete=RefActions.SET_NULL,
        ),
        doc="user primary group ID who created the message",
        nullable=True,
    ),
    sa.Column(
        "content",
        sa.String,
        nullable=False,
    ),
    sa.Column(
        "type",
        sa.Enum(ConversationMessageType),
        doc="Classification of the node associated to this task",
    ),
    column_created_datetime(timezone=True),
    column_modified_datetime(timezone=True),
    # indexes
    sa.Index(
        "idx_conversation_messages_created_desc",
        sa.desc("created"),
    ),
)
