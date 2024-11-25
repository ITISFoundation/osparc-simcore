import sqlalchemy as sa

from ._common import RefActions
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
        doc="Key name identifier for the service, without specifiying its versions",
    ),
    sa.Column(
        "service_version",
        sa.String,
        nullable=False,
        doc="Version of the service. Combined with 'service_key', it forms a unique identifier for this service.",
    ),
    # Tag
    sa.Column(
        "tag_id",
        sa.BigInteger,
        sa.ForeignKey(
            tags.c.id, onupdate=RefActions.CASCADE, ondelete=RefActions.CASCADE
        ),
        nullable=False,
        doc="Identifier of the tag assigned to this specific service (service_key, service_version).",
    ),
    # Constraints
    sa.ForeignKeyConstraint(
        ["service_key", "service_version"],
        ["services_meta_data.key", "services_meta_data.version"],
        onupdate=RefActions.CASCADE,
        ondelete=RefActions.CASCADE,
    ),
    sa.UniqueConstraint(
        "service_key", "service_version", "tag_id", name="services_tags_uc"
    ),
)
