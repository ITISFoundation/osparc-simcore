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
            name="fk_projects_to_products_project_uuid_projects",
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
        doc="Project unique ID",
    ),
    sa.Column(
        "product_name",
        sa.String,
        sa.ForeignKey(
            "products.name",
            name="fk_projects_to_products_name_products",
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
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
