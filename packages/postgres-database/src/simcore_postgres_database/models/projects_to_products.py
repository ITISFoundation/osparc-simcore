import sqlalchemy as sa

from ._common import column_created_datetime, column_modified_datetime
from .base import metadata

projects_to_products = sa.Table(
    "projects_to_products",
    metadata,
    sa.Column(
        "project_uuid",
        sa.String,
        sa.ForeignKey(
            "projects.uuid",
            onupdate="CASCADE",
            ondelete="CASCADE",
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
            onupdate="CASCADE",
            ondelete="CASCADE",
            name="fk_projects_to_products_product_name",
        ),
        nullable=False,
        doc="Products unique name",
    ),
    # TIME STAMPS ----
    column_created_datetime(),
    column_modified_datetime(),
    sa.UniqueConstraint("project_uuid", "product_name"),
)
