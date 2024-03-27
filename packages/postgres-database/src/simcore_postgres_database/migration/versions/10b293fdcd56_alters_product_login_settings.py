"""alters product.login_settings

Revision ID: 10b293fdcd56
Revises: 69957302b7ee
Create Date: 2023-01-14 21:12:56.182870+00:00

"""

import json

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "10b293fdcd56"
down_revision = "69957302b7ee"
branch_labels = None
depends_on = None


def upgrade():
    # Reassign items from two_factor_enabled -> LOGIN_2FA_REQUIRED
    conn = op.get_bind()
    rows = conn.execute(sa.DDL("SELECT name, login_settings FROM products")).fetchall()
    for row in rows:
        data = row["login_settings"] or {}
        if "two_factor_enabled" in data:
            data["LOGIN_2FA_REQUIRED"] = data.pop("two_factor_enabled")
            data = json.dumps(data)
            conn.execute(
                sa.DDL(
                    "UPDATE products SET login_settings = '{}' WHERE name = '{}'".format(  # nosec
                        data, row["name"]
                    )
                )
            )

    # change to nullable=True and remove the server default to
    op.alter_column(
        "products",
        "login_settings",
        server_default=sa.text("'{}'::jsonb"),
        existing_server_default=sa.text("'{\"two_factor_enabled\": false}'::jsonb"),
    )


def downgrade():
    # Reassign items from LOGIN_2FA_REQUIRED -> two_factor_enabled=false
    conn = op.get_bind()
    rows = conn.execute(sa.DDL("SELECT name, login_settings FROM products")).fetchall()
    for row in rows:
        data = row["login_settings"] or {}
        data["two_factor_enabled"] = data.pop(
            "LOGIN_2FA_REQUIRED", False
        )  # back to default
        data = json.dumps(data)
        conn.execute(
            sa.DDL(
                "UPDATE products SET login_settings = '{}' WHERE name = '{}'".format(  # nosec
                    data, row["name"]
                )
            )
        )

    # revert to nullable=False and add default
    op.alter_column(
        "products",
        "login_settings",
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        existing_server_default=sa.text("'{}'::jsonb"),
        server_default=sa.text("'{\"two_factor_enabled\": false}'::jsonb"),
    )
