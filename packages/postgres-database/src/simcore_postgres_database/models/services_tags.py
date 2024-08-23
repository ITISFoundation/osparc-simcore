import sqlalchemy as sa

from .base import metadata
from .tags import tags

services_tags = sa.Table(
    #
    # Tags assigned to a service (many-to-many relation)
    #
    "services_tags",
    metadata,
    # Service
    sa.Column(
        "service_key",
        sa.String,
        nullable=False,
        doc="Service Key Identifier",
    ),
    sa.Column(
        "service_version",
        sa.String,
        nullable=False,
        doc="Service version",
    ),
    # Tag
    sa.Column(
        "tag_id",
        sa.BigInteger,
        sa.ForeignKey(tags.c.id, onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
    ),
    # Constraints
    sa.ForeignKeyConstraint(
        ["service_key", "service_version"],
        ["services_meta_data.key", "services_meta_data.version"],
        onupdate="CASCADE",
        ondelete="CASCADE",
    ),
    sa.UniqueConstraint(
        "service_key", "service_version", "tag_id", name="services_tags_uc"
    ),
)
