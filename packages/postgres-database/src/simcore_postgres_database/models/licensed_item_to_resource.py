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
    sa.Column(
        "product_name",
        sa.String,
        sa.ForeignKey(
            "products.name",
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.CASCADE,
            name="fk_licensed_item_to_resource_product_name",
        ),
        nullable=False,
    ),
    column_created_datetime(timezone=True),
    column_modified_datetime(timezone=True),
    #########
    sa.PrimaryKeyConstraint(
        "licensed_item_id",
        "licensed_resource_id",
        name="pk_licensed_item_to_resource_item_and_resource_id",
    ),
    # NOTE: Currently, there is a constraint that a resource item ID cannot be in multiple licensed items.
    # The reason is that the license key and license version coming from the internal license server are part of the licensed resource domain.
    # Sim4Life performs a mapping on their side, where the license key and version are mapped to a licensed item.
    # If this constraint is broken, the mapping logic in Sim4Life might break.
    sa.UniqueConstraint(
        "product_name",
        "licensed_resource_id",
        name="uq_licensed_item_to_resource_resource_id",
    ),
)
