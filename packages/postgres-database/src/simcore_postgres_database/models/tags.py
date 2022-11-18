import sqlalchemy as sa

from .base import metadata

#
# tags: a way to mark any entity (e.g. a project, ...)
#       this can be used to perform operations as filter, select, compare, etc
#
tags = sa.Table(
    "tags",
    metadata,
    sa.Column(
        "id",
        sa.BigInteger(),
        nullable=False,
        primary_key=True,
    ),
    sa.Column(
        "name",
        sa.String(),
        nullable=False,
        doc="display name",
    ),
    sa.Column(
        "description",
        sa.String(),
        nullable=True,
        doc="description displayed",
    ),
    sa.Column(
        "color",
        sa.String(),
        nullable=False,
        doc="Hex color (see https://www.color-hex.com/)",
    ),
)


#
# tags_to_groups: Maps tags with groups to define the level of access
#                 of a group (group_id) for the corresponding tag (tag_id)
#
tags_to_groups = sa.Table(
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
            "groups.gid",
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
    sa.Column(
        "created",
        sa.DateTime(),
        nullable=False,
        server_default=sa.sql.func.now(),
        doc="Timestamp auto-generated upon creation",
    ),
    sa.Column(
        "modified",
        sa.DateTime(),
        nullable=False,
        server_default=sa.sql.func.now(),
        onupdate=sa.sql.func.now(),
        doc="Timestamp with last row update",
    ),
    sa.UniqueConstraint("tag_id", "group_id"),
)


#
# study_tags: projects marked with tags
#
study_tags = sa.Table(
    "study_tags",
    metadata,
    sa.Column(
        "study_id",
        sa.BigInteger,
        sa.ForeignKey("projects.id", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column(
        "tag_id",
        sa.BigInteger,
        sa.ForeignKey("tags.id", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.UniqueConstraint("study_id", "tag_id"),
)
