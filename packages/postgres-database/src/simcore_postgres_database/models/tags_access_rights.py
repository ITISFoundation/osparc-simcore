import sqlalchemy as sa

from ._common import RefActions, column_created_datetime, column_modified_datetime
from .base import metadata
from .groups import groups
from .tags import tags

tags_access_rights = sa.Table(
    #
    # Maps tags with groups to define the level of access rights
    # of a group (group_id) for the corresponding tag (tag_id)
    #
    "tags_access_rights",
    metadata,
    sa.Column(
        "tag_id",
        sa.BigInteger(),
        sa.ForeignKey(
            tags.c.id,
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.CASCADE,
            name="fk_tag_to_group_tag_id",
        ),
        nullable=False,
        doc="References the unique identifier of the tag that these access rights apply to.",
    ),
    sa.Column(
        "group_id",
        sa.BigInteger,
        sa.ForeignKey(
            groups.c.gid,
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.CASCADE,
            name="fk_tag_to_group_group_id",
        ),
        nullable=False,
        doc="References the unique identifier of the group that has access rights to the tag.",
    ),
    # ACCESS RIGHTS ---
    sa.Column(
        "read",
        sa.Boolean(),
        nullable=False,
        server_default=sa.sql.expression.true(),
        doc="Indicates whether the group has permission to view the tag. "
        "A value of 'True' allows the group to access the tag's details.",
    ),
    sa.Column(
        "write",
        sa.Boolean(),
        nullable=False,
        server_default=sa.sql.expression.false(),
        doc="Indicates whether the group has permission to modify the tag. "
        "A value of 'True' grants write access to the group.",
    ),
    sa.Column(
        "delete",
        sa.Boolean(),
        nullable=False,
        server_default=sa.sql.expression.false(),
        doc="Indicates whether the group has permission to delete the tag. "
        "A value of 'True' allows the group to remove the tag.",
    ),
    # TIME STAMPS ----
    column_created_datetime(timezone=False),
    column_modified_datetime(timezone=False),
    sa.UniqueConstraint("tag_id", "group_id"),
)
