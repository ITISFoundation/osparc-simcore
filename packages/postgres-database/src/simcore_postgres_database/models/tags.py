"""Tags table

- Represents tags that can be associated with various entities.

Migration strategy:
- The primary key is `id`, which is unique and sufficient for migration.
- Ensure foreign key references (if any) are valid in the target database.
- No additional changes are required; this table can be migrated as is.
"""

import sqlalchemy as sa

from .base import metadata

tags = sa.Table(
    #
    # A way to mark any entity (e.g. a project, ...)
    # this can be used to perform operations as filter, select, compare, etc
    #
    "tags",
    metadata,
    sa.Column(
        "id",
        sa.BigInteger(),
        nullable=False,
        primary_key=True,
        doc="Unique identifier for each tag.",
    ),
    sa.Column("name", sa.String(), nullable=False, doc="The display name of the tag."),
    sa.Column(
        "description",
        sa.String(),
        nullable=True,
        doc="A brief description displayed for the tag.",
    ),
    sa.Column(
        "color",
        sa.String(),
        nullable=False,
        doc="Hexadecimal color code representing the tag (e.g., #FF5733).",
    ),
    sa.Column(
        "priority",
        sa.Integer(),
        nullable=True,
        doc=(
            "Explicit ordering priority when displaying tags. "
            "Tags with a lower value are displayed first. "
            "If NULL, tags are considered to have the lowest priority and "
            "are displayed after non-NULL values, ordered by their ID (reflecting creation order)."
        ),
    ),
)
