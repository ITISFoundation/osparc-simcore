import sqlalchemy as sa

from ._common import column_created_datetime, column_modified_datetime
from .base import metadata
from .groups import groups
from .tags import tags

tags_to_groups = sa.Table(
    #
    # Maps tags with groups to define the level of access
    # of a group (group_id) for the corresponding tag (tag_id)
    #
    "tags_to_groups",
    metadata,
    sa.Column(
        "tag_id",
        sa.BigInteger(),
        sa.ForeignKey(
            tags.c.id,
            onupdate="CASCADE",
            ondelete="CASCADE",
            name="fk_tag_to_group_tag_id",
        ),
        nullable=False,
        doc="Tag unique ID",
    ),
    sa.Column(
        "group_id",
        sa.BigInteger,
        sa.ForeignKey(
            groups.c.gid,
            onupdate="CASCADE",
            ondelete="CASCADE",
            name="fk_tag_to_group_group_id",
        ),
        nullable=False,
        doc="Group unique ID",
    ),
    # ACCESS RIGHTS ---
    sa.Column(
        "read",
        sa.Boolean(),
        nullable=False,
        server_default=sa.sql.expression.true(),
        doc="If true, group can *read* a tag."
        "This column can be used to set the tag invisible",
    ),
    sa.Column(
        "write",
        sa.Boolean(),
        nullable=False,
        server_default=sa.sql.expression.false(),
        doc="If true, group can *create* and *update* a tag",
    ),
    sa.Column(
        "delete",
        sa.Boolean(),
        nullable=False,
        server_default=sa.sql.expression.false(),
        doc="If true, group can *delete* the tag",
    ),
    # TIME STAMPS ----
    column_created_datetime(timezone=False),
    column_modified_datetime(timezone=False),
    sa.UniqueConstraint("tag_id", "group_id"),
)
