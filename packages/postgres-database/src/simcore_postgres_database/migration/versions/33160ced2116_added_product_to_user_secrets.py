"""added product to user secrets

Revision ID: 33160ced2116
Revises: c9c165644731
Create Date: 2026-07-07 13:45:07.791420+00:00

"""

import sqlalchemy as sa
from alembic import op
from simcore_postgres_database.utils_users_secrets import FALLBACK_PRODUCT_NAME

# revision identifiers, used by Alembic.
revision = "33160ced2116"
down_revision = "c9c165644731"
branch_labels = None
depends_on = None


def upgrade():
    # add as nullable first so it can be backfilled
    op.add_column("users_secrets", sa.Column("product_name", sa.String(), nullable=True))

    # backfill existing rows: they used to be valid for every product
    op.execute(
        sa.DDL(
            f"""
        UPDATE users_secrets
        SET product_name = '{FALLBACK_PRODUCT_NAME}'
        WHERE product_name IS NULL
    """  # noqa: S608
        )
    )

    op.alter_column("users_secrets", "product_name", nullable=False)

    op.create_foreign_key(
        "fk_users_secrets_product_name_products",
        "users_secrets",
        "products",
        ["product_name"],
        ["name"],
        onupdate="CASCADE",
        ondelete="CASCADE",
    )

    # widen primary key to (user_id, product_name)
    op.drop_constraint("users_secrets_pkey", "users_secrets", type_="primary")
    op.create_primary_key("users_secrets_pkey", "users_secrets", ["user_id", "product_name"])


def downgrade():
    # collapse back to a single row per user: prefer the 'osparc' row, else the most
    # recently modified one, and drop the rest
    op.execute(
        sa.DDL(
            f"""
        DELETE FROM users_secrets
        WHERE (user_id, product_name) NOT IN (
            SELECT user_id, product_name
            FROM (
                SELECT
                    user_id,
                    product_name,
                    ROW_NUMBER() OVER (
                        PARTITION BY user_id
                        ORDER BY (product_name = '{FALLBACK_PRODUCT_NAME}') DESC, modified DESC
                    ) AS row_number
                FROM users_secrets
            ) ranked
            WHERE row_number = 1
        )
    """  # noqa: S608
        )
    )

    op.drop_constraint("users_secrets_pkey", "users_secrets", type_="primary")
    op.create_primary_key("users_secrets_pkey", "users_secrets", ["user_id"])

    op.drop_constraint("fk_users_secrets_product_name_products", "users_secrets", type_="foreignkey")
    op.drop_column("users_secrets", "product_name")
