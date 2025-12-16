"""Add product_name to projects

Revision ID: ce69cc44246a
Revises: a85557c02d71
Create Date: 2025-12-08 14:14:07.573764+00:00

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "ce69cc44246a"
down_revision = "a85557c02d71"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("projects", sa.Column("product_name", sa.String(), nullable=True))

    op.execute(
        """
        UPDATE projects
        SET product_name = ptp.product_name
        FROM projects_to_products ptp
        WHERE projects.uuid = ptp.project_uuid
        """
    )

    op.alter_column("projects", "product_name", nullable=False)

    op.create_foreign_key(
        "fk_projects_to_product_name",
        "projects",
        "products",
        ["product_name"],
        ["name"],
        onupdate="CASCADE",
        ondelete="CASCADE",
    )

    op.drop_table("projects_to_products")


def downgrade():
    op.create_table(
        "projects_to_products",
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
        sa.Column(
            "created",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "modified",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            autoincrement=False,
            nullable=False,
        ),
        sa.UniqueConstraint("project_uuid", "product_name"),
        sa.Index("idx_projects_to_products_product_name", "product_name"),
    )

    op.execute(
        """
        INSERT INTO projects_to_products (project_uuid, product_name, created, modified)
        SELECT uuid, product_name, NOW(), NOW()
        FROM projects
        WHERE product_name IS NOT NULL
        ON CONFLICT (project_uuid, product_name) DO NOTHING
        """
    )

    op.drop_constraint("fk_projects_to_product_name", "projects", type_="foreignkey")

    op.drop_column("projects", "product_name")
