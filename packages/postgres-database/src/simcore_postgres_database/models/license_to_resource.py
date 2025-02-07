import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from ._common import RefActions, column_created_datetime, column_modified_datetime
from .base import metadata

license_to_resource = sa.Table(
    "license_to_resource",
    metadata,
    sa.Column(
        "license_id",
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey(
            "licenses.license_id",
            name="fk_license_to_resource_license_id",
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.CASCADE,
        ),
        nullable=False,
    ),
    sa.Column(
        "licensed_resource_id",  # <-- This will be renamed to "licensed_resource_id"
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey(
            "licensed_resources.licensed_resource_id",  # <-- This will be renamed to "licensed_resource_id"
            name="fk_license_to_resource_licensed_resource_id",
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.CASCADE,
        ),
        nullable=False,
    ),
    column_created_datetime(timezone=True),
    column_modified_datetime(timezone=True),
)
