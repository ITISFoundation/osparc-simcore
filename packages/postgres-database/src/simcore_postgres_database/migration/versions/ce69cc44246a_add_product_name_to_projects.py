"""Add product_name to projects

Revision ID: ce69cc44246a
Revises: a85557c02d71
Create Date: 2025-12-08 14:14:07.573764+00:00

"""

import sqlalchemy as sa
from alembic import op

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


def downgrade():
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
