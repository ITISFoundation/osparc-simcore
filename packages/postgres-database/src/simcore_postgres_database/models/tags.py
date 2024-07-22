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
