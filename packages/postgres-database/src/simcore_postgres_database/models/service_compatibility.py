"""Service compatibility table

- Defines compatibility between services.

Migration strategy:
- Composite primary key (`service_key`, `service_version`) is unique and sufficient for migration.
- Ensure foreign key references (if any) are valid in the target database.
- No additional changes are required; this table can be migrated as is.
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from .base import metadata

service_compatibility = sa.Table(
    "service_compatibility",
    metadata,
    sa.Column(
        "service_key",
        sa.String,
        nullable=False,
        doc="Service key identifier",
    ),
    sa.Column(
        "service_version",
        sa.String,
        nullable=False,
        doc="Service version identifier",
    ),
    sa.Column(
        "compatibility",
        JSONB,
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
        doc="Compatibility information in JSON format",
    ),
    sa.PrimaryKeyConstraint("service_key", "service_version"),
)
