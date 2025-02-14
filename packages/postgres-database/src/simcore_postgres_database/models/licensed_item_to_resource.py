import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from ._common import RefActions, column_created_datetime, column_modified_datetime
from .base import metadata

licensed_item_to_resource = sa.Table(
    "licensed_item_to_resource",
    metadata,
    sa.Column(
        "licensed_item_id",
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey(
            "licensed_items.licensed_item_id",
            name="fk_licensed_item_to_resource_licensed_item_id",
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.CASCADE,
        ),
        nullable=False,
    ),
    sa.Column(
        "licensed_resource_id",
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey(
            "licensed_resources.licensed_resource_id",
            name="fk_licensed_item_to_resource_licensed_resource_id",
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.CASCADE,
        ),
        nullable=False,
    ),
    column_created_datetime(timezone=True),
    column_modified_datetime(timezone=True),
)
