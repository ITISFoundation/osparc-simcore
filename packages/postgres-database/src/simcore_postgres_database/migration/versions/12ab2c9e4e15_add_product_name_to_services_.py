"""add product_name to services_specifications

Revision ID: 12ab2c9e4e15
Revises: 7f85c4bf7aa1
Create Date: 2026-03-30 15:05:58.503996+00:00

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "12ab2c9e4e15"
down_revision = "7f85c4bf7aa1"
branch_labels = None
depends_on = None


def upgrade():
    # Step 1: Add product_name column as nullable first
    op.add_column(
        "services_specifications",
        sa.Column("product_name", sa.String(), nullable=True),
    )

    # Step 2: Backfill existing rows.
    # For each existing row, duplicate it for every product defined in the products table.
    # Then remove the original rows (with NULL product_name).
    conn = op.get_bind()

    # Duplicate existing specs for each product in the products table
    conn.execute(
        sa.text("""
        INSERT INTO services_specifications (service_key, service_version, gid, product_name, sidecar, service, comments)
        SELECT ss.service_key, ss.service_version, ss.gid, p.name, ss.sidecar, ss.service, ss.comments
        FROM services_specifications ss
        CROSS JOIN products p
        WHERE ss.product_name IS NULL
        ON CONFLICT DO NOTHING
    """)
    )

    # Delete rows that still have NULL product_name (they've been duplicated above)
    conn.execute(sa.text("DELETE FROM services_specifications WHERE product_name IS NULL"))

    # Step 3: Make column non-nullable
    op.alter_column("services_specifications", "product_name", nullable=False)

    # Step 4: Drop old primary key and create new one including product_name
    op.drop_constraint("services_specifications_pk", "services_specifications", type_="primary")
    op.create_primary_key(
        "services_specifications_pk",
        "services_specifications",
        ["service_key", "service_version", "gid", "product_name"],
    )

    # Step 5: Add foreign key to products table
    op.create_foreign_key(
        "fk_services_specifications_product_name_products",
        "services_specifications",
        "products",
        ["product_name"],
        ["name"],
        onupdate="CASCADE",
        ondelete="CASCADE",
    )


def downgrade():
    # Step 1: Drop FK constraint
    op.drop_constraint(
        "fk_services_specifications_product_name_products",
        "services_specifications",
        type_="foreignkey",
    )

    # Step 2: Drop new PK and recreate the old one without product_name.
    # First, remove duplicate rows that differ only by product_name
    conn = op.get_bind()
    conn.execute(
        sa.text("""
        DELETE FROM services_specifications
        WHERE ctid NOT IN (
            SELECT min(ctid)
            FROM services_specifications
            GROUP BY service_key, service_version, gid
        )
    """)
    )

    op.drop_constraint("services_specifications_pk", "services_specifications", type_="primary")
    op.create_primary_key(
        "services_specifications_pk",
        "services_specifications",
        ["service_key", "service_version", "gid"],
    )

    # Step 3: Drop product_name column
    op.drop_column("services_specifications", "product_name")
