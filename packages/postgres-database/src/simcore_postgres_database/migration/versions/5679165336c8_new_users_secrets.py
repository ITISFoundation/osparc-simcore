"""new users secrets

Revision ID: 5679165336c8
Revises: 61b98a60e934
Create Date: 2025-07-17 17:07:20.200038+00:00

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "5679165336c8"
down_revision = "61b98a60e934"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users_secrets",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column(
            "modified",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_users_secrets_user_id_users",
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", name="users_secrets_pkey"),
    )

    # Copy password data from users table to users_secrets table
    op.execute(
        sa.DDL(
            """
        INSERT INTO users_secrets (user_id, password_hash, modified)
        SELECT id, password_hash, created_at
        FROM users
        WHERE password_hash IS NOT NULL
    """
        )
    )

    op.drop_column("users", "password_hash")


def downgrade():
    op.add_column(
        "users",
        sa.Column("password_hash", sa.VARCHAR(), autoincrement=False, nullable=False),
    )

    # Copy password data back from users_secrets table to users table
    op.execute(
        sa.DDL(
            """
        UPDATE users
        SET password_hash = us.password_hash
        FROM users_secrets us
        WHERE users.id = us.user_id
    """
        )
    )

    op.drop_table("users_secrets")
