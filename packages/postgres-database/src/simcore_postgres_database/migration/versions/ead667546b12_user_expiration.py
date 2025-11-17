"""User expiration

Revision ID: ead667546b12
Revises: 9d477e20d06e
Create Date: 2022-09-12 14:09:04.385524+00:00

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "ead667546b12"
down_revision = "9d477e20d06e"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("expires_at", sa.DateTime(), nullable=True))

    # https://medium.com/makimo-tech-blog/upgrading-postgresqls-enum-type-with-sqlalchemy-using-alembic-migration-881af1e30abe
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE userstatus ADD VALUE 'EXPIRED'")


def downgrade():
    op.drop_column("users", "expires_at")

    # https://medium.com/makimo-tech-blog/upgrading-postgresqls-enum-type-with-sqlalchemy-using-alembic-migration-881af1e30abe
    op.execute("ALTER TYPE userstatus RENAME TO userstatus_old")
    op.execute(
        "CREATE TYPE userstatus AS ENUM('CONFIRMATION_PENDING', 'ACTIVE', 'BANNED')"
    )
    op.execute(
        "ALTER TABLE users ALTER COLUMN status TYPE userstatus USING "
        "status::text::userstatus"
    )
    op.execute("DROP TYPE userstatus_old")
