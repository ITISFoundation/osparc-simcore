import sqlalchemy as sa

from ._common import column_created_datetime, column_modified_datetime
from .base import metadata

#
# internet_to_groups: Maps internet access permissions to groups
#
internet_to_groups = sa.Table(
    "internet_to_groups",
    metadata,
    sa.Column(
        "group_id",
        sa.BigInteger,
        sa.ForeignKey(
            "groups.gid",
            onupdate="CASCADE",
            ondelete="CASCADE",
            name="fk_tag_to_group_group_id",
        ),
        nullable=False,
        doc="Group unique ID",
    ),
    sa.Column(
        "has_access",
        sa.Boolean(),
        nullable=False,
        server_default=sa.sql.expression.true(),
        doc="If true, group has internet access. "
        "If a user is part of this group, it's "
        "service can access the internet.",
    ),
    # TIME STAMPS ----
    column_created_datetime(),
    column_modified_datetime(),
    sa.UniqueConstraint("group_id"),
)
