import enum

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from ._common import RefActions, column_created_datetime, column_modified_datetime
from .base import metadata
from .groups import groups
from .projects import projects


class ConversationType(enum.Enum):
    PROJECT_STATIC = "PROJECT_STATIC"  # Static conversation for the project
    PROJECT_ANNOTATION = "PROJECT_ANNOTATION"  # Something like sticky note, can be located anywhere in the pipeline UI
    SUPPORT = "SUPPORT"  # Support conversation


conversations = sa.Table(
    "conversations",
    metadata,
    sa.Column(
        "conversation_id",
        UUID(as_uuid=True),
        nullable=False,
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    ),
    sa.Column(
        "name",
        sa.String,
        nullable=False,
    ),
    sa.Column(
        "project_uuid",
        sa.String,
        sa.ForeignKey(
            projects.c.uuid,
            name="fk_projects_conversations_project_uuid",
            ondelete=RefActions.CASCADE,
            onupdate=RefActions.CASCADE,
        ),
        index=True,
        nullable=True,
    ),
    # NOTE: if the user primary group ID gets deleted, it sets to null which should be interpreted as "unknown" user
    sa.Column(
        "user_group_id",
        sa.BigInteger,
        sa.ForeignKey(
            groups.c.gid,
            name="fk_conversations_user_primary_gid",
            ondelete=RefActions.SET_NULL,
        ),
        doc="user primary group ID who created the message",
        nullable=True,
    ),
    sa.Column(
        "type",
        sa.Enum(ConversationType),
        doc="Classification of the node associated to this task",
    ),
    sa.Column(
        "product_name",
        sa.String,
        sa.ForeignKey(
            "products.name",
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.CASCADE,
            name="fk_conversations_product_name",
        ),
        nullable=False,
        doc="Product name identifier. If None, then the item is not exposed",
    ),
    sa.Column(
        "extra_context",
        JSONB,
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
        doc="Free JSON to store extra context",
    ),
    column_created_datetime(timezone=True),
    column_modified_datetime(timezone=True),
)
