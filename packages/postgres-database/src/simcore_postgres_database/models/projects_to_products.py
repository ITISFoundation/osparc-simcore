"""Projects to products table

- Links projects to products.

Migration strategy:
- Composite primary key (`project_id`, `product_id`) is unique and sufficient for migration.
- Ensure foreign key references to `projects` and `products` are valid in the target database.
- No additional changes are required; this table can be migrated as is.
"""

import sqlalchemy as sa

from ._common import RefActions, column_created_datetime, column_modified_datetime
from .base import metadata

projects_to_products = sa.Table(
    "projects_to_products",
    metadata,
    sa.Column(
        "project_uuid",
        sa.String,
        sa.ForeignKey(
            "projects.uuid",
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.CASCADE,
            name="fk_projects_to_products_product_uuid",
        ),
        nullable=False,
        doc="Project unique ID",
    ),
    sa.Column(
        "product_name",
        sa.String,
        sa.ForeignKey(
            "products.name",
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.CASCADE,
            name="fk_projects_to_products_product_name",
        ),
        nullable=False,
        doc="Products unique name",
    ),
    # TIME STAMPS ----
    column_created_datetime(timezone=False),
    column_modified_datetime(timezone=False),
    sa.UniqueConstraint("project_uuid", "product_name"),
    sa.Index("idx_projects_to_products_product_name", "product_name"),
)
