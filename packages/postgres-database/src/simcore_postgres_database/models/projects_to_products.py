import sqlalchemy as sa

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
    # -----
    sa.Column(
        "created",
        sa.DateTime(),
        nullable=False,
        server_default=sa.sql.func.now(),
        doc="Timestamp auto-generated upon creation",
    ),
    sa.Column(
        "modified",
        sa.DateTime(),
        nullable=False,
        server_default=sa.sql.func.now(),
        onupdate=sa.sql.func.now(),
        doc="Timestamp with last row update",
    ),
    sa.UniqueConstraint("project_uuid", "product_name"),
)
